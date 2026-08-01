"""Gün sonu değerlendirmesi — kural tabanlı yorum varsayılan.

`_varsayilan_yorum_uret`, `yorum_uret` parametresiyle değiştirilebilir bir seam:
`ui/app.py` bunun yerine `core.services.ai_advisor.yorum_uret`'i geçirerek gerçek
bir Gemini çağrısına düşürür (bkz. ai_advisor.py).
"""

from datetime import date
from typing import Callable

from core.database import SessionLocal
from core.models import Task
from core.services import planning_service


def _varsayilan_yorum_uret(
    tamamlama_orani: int,
    planlanan_sayisi: int,
    tamamlanan_sayisi: int,
    tamamlanmayanlar: list[str] | None = None,
) -> str:
    """Son parametre kural tabanlı yorumda kullanılmaz — yalnızca
    `core.services.ai_advisor.yorum_uret` ile aynı imzada kalmak için var."""
    if tamamlama_orani == 100:
        return (
            f"Harika! Planladığın {planlanan_sayisi} görevin tamamını bitirdin. "
            "**Bu tempo verimliliğini istikrarlı şekilde artırır.**"
        )
    if tamamlama_orani >= 70:
        return (
            f"İyi gidiyorsun — {planlanan_sayisi} görevden {tamamlanan_sayisi}'ini tamamladın. "
            "Kalanları yarına taşımayı düşün."
        )
    if tamamlama_orani >= 40:
        return (
            f"Planın yarısından biraz fazlası gerçekleşti ({tamamlanan_sayisi}/{planlanan_sayisi}). "
            "**Daha az görev planlamak tamamlama oranını artırabilir.**"
        )
    return (
        f"Bugün planlanan {planlanan_sayisi} görevden sadece {tamamlanan_sayisi} tanesi bitti. "
        "Yarın için daha gerçekçi/az sayıda görev planlamayı dene."
    )


def gun_sonu_degerlendirmesi_uret(
    user_id: int, gun: date, yorum_uret: Callable = _varsayilan_yorum_uret,
) -> dict | None:
    """Verilen günün planına göre gerçekleşme durumunu değerlendirir.

    O gün için plan yoksa (veya plan boşsa) None döner — değerlendirilecek bir şey yok.
    """
    kayit = planning_service.son_plan(user_id, gun)
    if kayit is None or not kayit.dilimler:
        return None

    task_idler = [d["task_id"] for d in kayit.dilimler if d.get("task_id") is not None]
    with SessionLocal() as session:
        gorevler = {
            t.id: t
            for t in session.query(Task).filter(Task.id.in_(task_idler)).all()
        } if task_idler else {}

    tamamlananlar = [
        d for d in kayit.dilimler
        if gorevler.get(d.get("task_id")) is not None and gorevler[d["task_id"]].completed_at is not None
    ]
    tamamlanmayanlar = [d for d in kayit.dilimler if d not in tamamlananlar]

    planlanan_sayisi = len(kayit.dilimler)
    tamamlanan_sayisi = len(tamamlananlar)
    tamamlama_orani = round(tamamlanan_sayisi / planlanan_sayisi * 100)
    tamamlanan_dakika = sum(d["duration_minutes"] for d in tamamlananlar)

    return {
        "planlanan_sayisi": planlanan_sayisi,
        "tamamlanan_sayisi": tamamlanan_sayisi,
        "tamamlama_orani": tamamlama_orani,
        "planlanan_dakika": kayit.toplam_is_dakika,
        "tamamlanan_dakika": tamamlanan_dakika,
        "tamamlanmayanlar": [d["title"] for d in tamamlanmayanlar],
        "yorum": yorum_uret(
            tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi,
            tamamlanmayanlar=[d["title"] for d in tamamlanmayanlar],
        ),
    }
