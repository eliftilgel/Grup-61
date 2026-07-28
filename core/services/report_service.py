"""Haftalık verimlilik/erteleme raporu — kural tabanlı analiz metni (OpenAI'sız).

`_analiz_metni_uret` de `planning_service.gerekce_uret` ile aynı felsefeyle
değiştirilebilir bir seam: ileride gerçek bir OpenAI çağrısıyla değiştirilebilir.
"""

from datetime import date, time, timedelta

from core.database import SessionLocal
from core.models import PlanKaydi, Task

BUCKETS = [
    (time(7, 0), time(10, 0)),
    (time(10, 0), time(13, 0)),
    (time(13, 0), time(16, 0)),
    (time(16, 0), time(19, 0)),
    (time(19, 0), time(22, 0)),
]
BUCKET_ETIKETLERI = ["07–10", "10–13", "13–16", "16–19", "19–22"]
EN_COK_ERTELENEN_LIMIT = 5


def _dk(t: time) -> int:
    return t.hour * 60 + t.minute


def _saat_str_to_dk(s: str) -> int:
    saat, dakika = s.split(":")
    return int(saat) * 60 + int(dakika)


def _son_planlar(baslangic: date, bitis: date, session) -> list[PlanKaydi]:
    """Verilen aralıktaki her gün için sadece en son oluşturulan PlanKaydi'yi döner."""
    tumu = (
        session.query(PlanKaydi)
        .filter(PlanKaydi.gun >= baslangic, PlanKaydi.gun <= bitis)
        .order_by(PlanKaydi.created_at.desc())
        .all()
    )
    en_sonlar: dict[date, PlanKaydi] = {}
    for kayit in tumu:
        en_sonlar.setdefault(kayit.gun, kayit)  # desc sıralı olduğu için ilk görülen = en yeni
    return list(en_sonlar.values())


def _analiz_metni_uret(saat_dilimi_verimi: dict[str, int]) -> str:
    if not saat_dilimi_verimi or not any(saat_dilimi_verimi.values()):
        return "Bu hafta için yeterli veri yok — bir plan oluşturup tamamladığında burada analiz görünecek."
    en_dusuk_etiket = min(saat_dilimi_verimi, key=saat_dilimi_verimi.get)
    en_dusuk_yuzde = saat_dilimi_verimi[en_dusuk_etiket]
    return (
        f"Bu hafta {en_dusuk_etiket} arası verimin belirgin şekilde düşüyor (%{en_dusuk_yuzde}). "
        "Kritik görevleri bu dilime koymamanı öneririm. "
        "**Görevlerini sabah ilk işe alırsan tamamlama oranın artar.**"
    )


def haftalik_rapor(bitis: date | None = None, gun_sayisi: int = 7) -> dict:
    """[bitis - gun_sayisi + 1, bitis] aralığı için Rapor ekranının tüm sayılarını döner."""
    bitis = bitis or date.today()
    baslangic = bitis - timedelta(days=gun_sayisi - 1)

    with SessionLocal() as session:
        gorevler = (
            session.query(Task)
            .filter(Task.due_date >= baslangic, Task.due_date <= bitis)
            .all()
        )
        toplam = len(gorevler)
        tamamlanan = [t for t in gorevler if t.completed_at is not None]
        ertelenen = [t for t in gorevler if t.postponement_count > 0]

        verimlilik_orani = round(len(tamamlanan) / toplam * 100) if toplam else 0
        erteleme_orani = round(len(ertelenen) / toplam * 100) if toplam else 0

        en_cok_ertelenenler = [
            f"{t.title} — {t.postponement_count} kez ertelendi"
            for t in sorted(ertelenen, key=lambda t: (-t.postponement_count, t.title))[
                :EN_COK_ERTELENEN_LIMIT
            ]
        ]

        planlar = _son_planlar(baslangic, bitis, session)
        gecen_task_idler = {
            dilim.get("task_id") for kayit in planlar for dilim in kayit.dilimler
        }
        gecen_task_idler.discard(None)
        tamamlanma_by_id = {
            t.id: t.completed_at is not None
            for t in session.query(Task).filter(Task.id.in_(gecen_task_idler)).all()
        } if gecen_task_idler else {}

        bucket_toplam = [0] * len(BUCKETS)
        bucket_tamam = [0] * len(BUCKETS)
        for kayit in planlar:
            for dilim in kayit.dilimler:
                baslangic_dk = _saat_str_to_dk(dilim["start"])
                for i, (b_baslangic, b_bitis) in enumerate(BUCKETS):
                    if _dk(b_baslangic) <= baslangic_dk < _dk(b_bitis):
                        bucket_toplam[i] += 1
                        if tamamlanma_by_id.get(dilim.get("task_id"), False):
                            bucket_tamam[i] += 1
                        break

        saat_dilimi_verimi = {
            etiket: (round(bucket_tamam[i] / bucket_toplam[i] * 100) if bucket_toplam[i] else 0)
            for i, etiket in enumerate(BUCKET_ETIKETLERI)
        }

    return {
        "verimlilik_orani": verimlilik_orani,
        "erteleme_orani": erteleme_orani,
        "tamamlanan_sayisi": len(tamamlanan),
        "ertelenen_sayisi": len(ertelenen),
        "saat_dilimi_verimi": saat_dilimi_verimi,
        "en_cok_ertelenenler": en_cok_ertelenenler,
        "analiz_metni": _analiz_metni_uret(saat_dilimi_verimi),
    }
