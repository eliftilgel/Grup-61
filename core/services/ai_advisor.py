"""Gemini tabanlı gerçek AI entegrasyonu.

planning_service/report_service/degerlendirme_service'teki kural tabanlı seam'leri
zenginleştirir. Her fonksiyon "sessizce başarısız olur" felsefesiyle yazıldı: API
anahtarı yoksa veya Gemini çağrısı herhangi bir sebeple patlarsa loglanır, çağıran
kural tabanlı sonucu (değişmeden) kullanmaya devam eder — kullanıcı akışı kesilmez.
"""

import json
import logging

from pydantic import BaseModel

from core.config import settings
from core.database import SessionLocal
from core.models import PlanKaydi, Task
from core.services.degerlendirme_service import _varsayilan_yorum_uret
from core.services.report_service import _analiz_metni_uret

logger = logging.getLogger(__name__)


def etkin() -> bool:
    """Gemini entegrasyonu aktif mi (API anahtarı tanımlı mı)."""
    return bool(settings.gemini_api_key)


def _client():
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


class _GerekceOgesi(BaseModel):
    task_id: int
    gerekce: str


class _GerekceYaniti(BaseModel):
    gerekceler: list[_GerekceOgesi]


def _gerekce_prompt_uret(dilimler: list[dict], gorevler: dict[int, Task], profil) -> str:
    satirlar = []
    for d in dilimler:
        task = gorevler.get(d.get("task_id"))
        satirlar.append(
            {
                "task_id": d.get("task_id"),
                "title": d["title"],
                "start": d["start"],
                "end": d["end"],
                "duration_minutes": d["duration_minutes"],
                "havuzdan": d["havuzdan"],
                "priority": task.priority if task else None,
                "teslim_tipi": task.teslim_tipi if task else None,
                "sabit_saat": task.sabit_saat.strftime("%H:%M") if task and task.sabit_saat else None,
            }
        )
    return (
        "Sen bir üretkenlik koçusun. Aşağıda bir kullanıcının bugünkü plan "
        "yerleştirmeleri var. Her görev için, neden bu saate yerleştirildiğini "
        "açıklayan kısa (1-2 cümle), motive edici, samimi bir Türkçe gerekçe metni yaz.\n\n"
        f"Kullanıcının en verimli saat aralığı: {profil.verimli_baslangic:%H:%M}-"
        f"{profil.verimli_bitis:%H:%M}. Uyku saatleri: {profil.uyku_baslangic:%H:%M}-"
        f"{profil.uyku_bitis:%H:%M}.\n\n"
        f"Görevler: {json.dumps(satirlar, ensure_ascii=False)}\n\n"
        "Her task_id için tam olarak bir gerekçe üret; id'leri değiştirme, atlama "
        "veya uydurma."
    )


def gerekceleri_zenginlestir(kayit_id: int, profil) -> None:
    """Zaten kaydedilmiş bir PlanKaydi'nin gerekçelerini tek bir toplu Gemini
    çağrısıyla zenginleştirir ve DB'yi günceller. Herhangi bir hata durumunda
    hiçbir şey yapmaz — kural tabanlı gerekçeler DB'de olduğu gibi kalır."""
    if not etkin():
        return
    try:
        from google.genai import types

        with SessionLocal() as session:
            kayit = session.get(PlanKaydi, kayit_id)
            if kayit is None or not kayit.dilimler:
                return
            task_idler = [d["task_id"] for d in kayit.dilimler if d.get("task_id") is not None]
            gorevler = (
                {t.id: t for t in session.query(Task).filter(Task.id.in_(task_idler)).all()}
                if task_idler
                else {}
            )
            prompt = _gerekce_prompt_uret(kayit.dilimler, gorevler, profil)
            yanit = _client().models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", response_schema=_GerekceYaniti,
                ),
            )
            ayristirilan = _GerekceYaniti.model_validate_json(yanit.text)
            yeni_gerekceler = {oge.task_id: oge.gerekce for oge in ayristirilan.gerekceler}
            kayit.dilimler = [
                {**d, "gerekce": yeni_gerekceler.get(d.get("task_id"), d["gerekce"])}
                for d in kayit.dilimler
            ]
            session.commit()
    except Exception:
        logger.exception(
            "Gemini ile gerekçe zenginleştirme başarısız oldu (plan id=%s) — "
            "kural tabanlı gerekçeler korunuyor.",
            kayit_id,
        )


def analiz_metni_uret(saat_dilimi_verimi: dict[str, int]) -> str:
    """report_service._analiz_metni_uret ile aynı imza — yerine geçebilir."""
    if not etkin():
        return _analiz_metni_uret(saat_dilimi_verimi)
    try:
        dilim_ozeti = ", ".join(f"{k}: %{v}" for k, v in saat_dilimi_verimi.items())
        prompt = (
            "Sen bir üretkenlik koçusun. Kullanıcının bu haftaki saat dilimi bazlı "
            f"görev tamamlama yüzdeleri: {dilim_ozeti}.\n\n"
            "Bu verilere dayanarak, kullanıcıya 2-3 cümlelik, motive edici, somut bir "
            "öneri içeren Türkçe bir analiz metni yaz. En düşük verimli dilime dikkat "
            "çek ve iyileştirme önerisi sun. Sadece düz metin döndür, JSON kullanma, "
            "markdown başlığı ekleme."
        )
        yanit = _client().models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _analiz_metni_uret(saat_dilimi_verimi)
    except Exception:
        logger.exception("Gemini ile analiz metni üretimi başarısız oldu — kural tabanlı metne dönülüyor.")
        return _analiz_metni_uret(saat_dilimi_verimi)


def yorum_uret(tamamlama_orani: int, planlanan_sayisi: int, tamamlanan_sayisi: int) -> str:
    """degerlendirme_service._varsayilan_yorum_uret ile aynı imza — yerine geçebilir."""
    if not etkin():
        return _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)
    try:
        prompt = (
            "Sen bir üretkenlik koçusun. Kullanıcı bugün "
            f"{planlanan_sayisi} görev planladı, {tamamlanan_sayisi} tanesini tamamladı "
            f"(%{tamamlama_orani} tamamlama oranı). Buna dayanarak 2-3 cümlelik, motive "
            "edici/yapıcı bir Türkçe gün sonu yorumu yaz. Sadece düz metin döndür."
        )
        yanit = _client().models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)
    except Exception:
        logger.exception("Gemini ile gün sonu yorumu üretimi başarısız oldu — kural tabanlı yoruma dönülüyor.")
        return _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)
