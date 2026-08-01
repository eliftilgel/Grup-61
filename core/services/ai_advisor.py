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
from core.services.planning_service import _genel_tavsiye_uret as _varsayilan_genel_tavsiye_uret
from core.services.planning_service import erteleme_onerisi_uret as _varsayilan_erteleme_onerisi_uret
from core.services.report_service import _analiz_metni_uret

logger = logging.getLogger(__name__)


def etkin() -> bool:
    """Gemini entegrasyonu aktif mi (API anahtarı tanımlı mı)."""
    return bool(settings.gemini_api_key)


def _client():
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


# Önemli: _client()'ın dönüşünü her zaman bir değişkene ata, sonra .models.generate_content
# çağır — `_client().models.generate_content(...)` şeklinde zincirlersen SDK'nın arka planda
# kullandığı async httpx istemcisi istek tamamlanmadan kapanıyor ("Cannot send a request, as
# the client has been closed" hatası). google-genai + Python 3.14 kombinasyonunda gözlemlendi.


class _GerekceOgesi(BaseModel):
    task_id: int
    gerekce: str


class _GerekceYaniti(BaseModel):
    gerekceler: list[_GerekceOgesi]


def _gerekce_prompt_uret(kayit: PlanKaydi, gorevler: dict[int, Task], profil) -> str:
    satirlar = []
    for d in kayit.dilimler:
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
        "Sen deneyimli bir üretkenlik koçusun. Aşağıda bir kullanıcının bugünkü plan "
        "yerleştirmeleri ve günün genel bağlamı var. Her görev için, neden bu saate "
        "yerleştirildiğini açıklayan kısa (1-2 cümle), motive edici, somut bir Türkçe "
        "gerekçe metni yaz. Klişe/genel ifadelerden kaçın — görev başlığına gerçekten "
        "referans ver, günün geri kalanıyla (toplam iş yükü, boş zaman) tutarlı ol.\n\n"
        f"Kullanıcının en verimli saat aralığı: {profil.verimli_baslangic:%H:%M}-"
        f"{profil.verimli_bitis:%H:%M}. Uyku saatleri: {profil.uyku_baslangic:%H:%M}-"
        f"{profil.uyku_bitis:%H:%M}.\n\n"
        f"Günün toplamı: {kayit.toplam_is_dakika} dakika iş, {kayit.bos_zaman_dakika} "
        f"dakika boş zaman. Genel değerlendirme: {kayit.genel_tavsiye}\n\n"
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
            prompt = _gerekce_prompt_uret(kayit, gorevler, profil)
            client = _client()
            yanit = client.models.generate_content(
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


def analiz_metni_uret(
    saat_dilimi_verimi: dict[str, int],
    verimlilik_orani: int | None = None,
    erteleme_orani: int | None = None,
    en_cok_ertelenenler: list[str] | None = None,
) -> str:
    """report_service._analiz_metni_uret ile aynı imza (+ opsiyonel zenginleştirme
    parametreleri) — yerine geçebilir."""
    if not etkin():
        return _analiz_metni_uret(saat_dilimi_verimi)
    try:
        dilim_ozeti = ", ".join(f"{k}: %{v}" for k, v in saat_dilimi_verimi.items())
        ek_baglam = ""
        if verimlilik_orani is not None:
            ek_baglam += f"\nHaftalık genel verimlilik oranı: %{verimlilik_orani}."
        if erteleme_orani is not None:
            ek_baglam += f" Haftalık erteleme oranı: %{erteleme_orani}."
        if en_cok_ertelenenler:
            ek_baglam += f"\nEn çok ertelenen görevler: {', '.join(en_cok_ertelenenler)}."
        prompt = (
            "Sen deneyimli bir üretkenlik koçusun. Kullanıcının bu haftaki saat dilimi "
            f"bazlı görev tamamlama yüzdeleri: {dilim_ozeti}.{ek_baglam}\n\n"
            "Bu verilerin tamamına dayanarak, kullanıcıya 2-4 cümlelik, motive edici, "
            "somut ve eyleme dönük bir Türkçe haftalık koçluk özeti yaz. En düşük verimli "
            "dilime ve (varsa) en çok ertelenen görevlere doğrudan değin, tek bir "
            "iyileştirme önerisi sun. Genel geçer/klişe cümlelerden kaçın. Sadece düz "
            "metin döndür, JSON kullanma, markdown başlığı ekleme."
        )
        client = _client()
        yanit = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _analiz_metni_uret(saat_dilimi_verimi)
    except Exception:
        logger.exception("Gemini ile analiz metni üretimi başarısız oldu — kural tabanlı metne dönülüyor.")
        return _analiz_metni_uret(saat_dilimi_verimi)


def yorum_uret(
    tamamlama_orani: int,
    planlanan_sayisi: int,
    tamamlanan_sayisi: int,
    tamamlanmayanlar: list[str] | None = None,
) -> str:
    """degerlendirme_service._varsayilan_yorum_uret ile aynı imza (+ opsiyonel
    tamamlanmayanlar parametresi) — yerine geçebilir."""
    if not etkin():
        return _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)
    try:
        kalanlar_cumlesi = (
            f" Kalan görevler: {', '.join(tamamlanmayanlar)}." if tamamlanmayanlar else ""
        )
        prompt = (
            "Sen deneyimli bir üretkenlik koçusun. Kullanıcı bugün "
            f"{planlanan_sayisi} görev planladı, {tamamlanan_sayisi} tanesini tamamladı "
            f"(%{tamamlama_orani} tamamlama oranı).{kalanlar_cumlesi}\n\n"
            "Buna dayanarak 2-3 cümlelik, motive edici/yapıcı bir Türkçe gün sonu yorumu "
            "yaz. Kalan görevler belirtildiyse en azından birine isim vererek somut bir "
            "öneri sun (ör. yarın hangisiyle başlanmalı). Genel geçer/klişe cümlelerden "
            "kaçın. Sadece düz metin döndür."
        )
        client = _client()
        yanit = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)
    except Exception:
        logger.exception("Gemini ile gün sonu yorumu üretimi başarısız oldu — kural tabanlı yoruma dönülüyor.")
        return _varsayilan_yorum_uret(tamamlama_orani, planlanan_sayisi, tamamlanan_sayisi)


class _SiraYaniti(BaseModel):
    sira: list[int]  # task_id'ler, önerilen çalışma sırasında


def _esnek_gorevler(gorevler: list[Task]) -> list[Task]:
    """`planning_service._sirali_gorevler_uret`'teki grup 2 tanımıyla birebir aynı:
    sabit saatli olmayan, kesin teslimli olmayan, havuzdan gelmeyen (bugüne ait) görevler."""
    return [t for t in gorevler if t.sabit_saat is None and t.teslim_tipi != "kesin" and t.due_date is not None]


def siralama_onerisi_uret(gorevler: list[Task], profil, enerji_seviyesi: str | None) -> dict[int, int] | None:
    """Bugüne ait esnek görevler için Gemini'den bütüncül bir çalışma sırası önerisi
    ister. Sabit saatli/kesin teslimli/havuzdan görevler bu kararın dışında tutulur —
    onların yerleşimi her zaman deterministik kalır. Gemini'nin döndürdüğü id kümesi
    beklenen kümeyle birebir eşleşmezse (eksik/fazla/tekrar) veya çağrı herhangi bir
    sebeple başarısız olursa None döner; çağıran (planning_service) bu durumda kural
    tabanlı sıralamayı kullanır — geçersiz/eksik bir sıralama asla plana sızmaz."""
    if not etkin():
        return None
    esnek = _esnek_gorevler(gorevler)
    if len(esnek) < 2:
        return None  # tek görevde veya hiç görev yokken sıralama kararı anlamsız
    try:
        from google.genai import types

        satirlar = [
            {
                "task_id": t.id,
                "title": t.title,
                "priority": t.priority,
                "duration_minutes": t.duration_minutes,
            }
            for t in esnek
        ]
        enerji_notu = f" Kullanıcının bugünkü enerji seviyesi: {enerji_seviyesi}." if enerji_seviyesi else ""
        prompt = (
            "Sen deneyimli bir üretkenlik koçusun. Aşağıda bugün için planlanacak, "
            "esnek saatli görevler var (priority: 1=düşük, 2=orta, 3=kritik). Bu "
            "görevleri, kullanıcının gününü en verimli şekilde geçirmesini sağlayacak "
            "bir çalışma sırasına diz — yalnızca önceliğe/süreye değil, görev "
            "başlıklarının içeriğine de bak (ör. birbiriyle ilişkili işleri art arda "
            f"yapmak, bilişsel yükü kademeli artırıp azaltmak).{enerji_notu}\n\n"
            f"Görevler: {json.dumps(satirlar, ensure_ascii=False)}\n\n"
            "Yalnızca verilen task_id'lerin tamamını, önerdiğin sırada, hiçbirini "
            "atlamadan veya tekrar etmeden bir liste olarak döndür."
        )
        client = _client()
        yanit = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=_SiraYaniti,
            ),
        )
        ayristirilan = _SiraYaniti.model_validate_json(yanit.text)
        beklenen_idler = {t.id for t in esnek}
        if len(ayristirilan.sira) != len(beklenen_idler) or set(ayristirilan.sira) != beklenen_idler:
            logger.warning(
                "Gemini sıralama önerisi beklenen id kümesiyle eşleşmiyor — "
                "kural tabanlı sıralamaya düşülüyor."
            )
            return None
        return {task_id: sira for sira, task_id in enumerate(ayristirilan.sira)}
    except Exception:
        logger.exception("Gemini ile sıralama önerisi üretimi başarısız oldu — kural tabanlı sıralamaya dönülüyor.")
        return None


def genel_tavsiye_uret(
    kritik_tercih_penceresinde: int, toplam_kritik: int, enerji_seviyesi: str | None = None,
) -> str:
    """planning_service._genel_tavsiye_uret ile aynı imza — yerine geçebilir."""
    if not etkin():
        return _varsayilan_genel_tavsiye_uret(kritik_tercih_penceresinde, toplam_kritik, enerji_seviyesi)
    try:
        enerji_notu = f" Bugünkü enerji seviyesi: {enerji_seviyesi}." if enerji_seviyesi else ""
        prompt = (
            "Sen deneyimli bir üretkenlik koçusun. Kullanıcının bugünkü planında "
            f"{toplam_kritik} kritik öncelikli görev var, bunlardan "
            f"{kritik_tercih_penceresinde} tanesi kullanıcının en verimli saat "
            f"aralığına yerleşti.{enerji_notu}\n\n"
            "Buna dayanarak 2-3 cümlelik, motive edici ve somut bir Türkçe genel gün "
            "tavsiyesi yaz. Genel geçer/klişe cümlelerden kaçın. Sadece düz metin döndür."
        )
        client = _client()
        yanit = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _varsayilan_genel_tavsiye_uret(kritik_tercih_penceresinde, toplam_kritik, enerji_seviyesi)
    except Exception:
        logger.exception("Gemini ile genel tavsiye üretimi başarısız oldu — kural tabanlı tavsiyeye dönülüyor.")
        return _varsayilan_genel_tavsiye_uret(kritik_tercih_penceresinde, toplam_kritik, enerji_seviyesi)


def erteleme_onerisi_uret(task: Task, profil=None) -> str:
    """planning_service.erteleme_onerisi_uret ile aynı imza — yerine geçebilir."""
    if not etkin():
        return _varsayilan_erteleme_onerisi_uret(task, profil)
    try:
        profil_notu = (
            f" Kullanıcının en verimli saati: {profil.verimli_baslangic:%H:%M}." if profil else ""
        )
        prompt = (
            "Sen deneyimli bir üretkenlik koçusun. Kullanıcının "
            f"'{task.title}' adlı görevi {task.postponement_count} kez ertelendi, "
            f"{task.duration_minutes} dakika sürüyor.{profil_notu}\n\n"
            "Buna dayanarak, görevi neden erteliyor olabileceğini düşünüp somut, "
            "1-2 cümlelik bir Türkçe öneri yaz (ör. bölme, farklı saate alma, "
            "zorluğu azaltma gibi spesifik bir adım öner). Genel geçer cümlelerden "
            "kaçın. Sadece düz metin döndür."
        )
        client = _client()
        yanit = client.models.generate_content(model=settings.gemini_model, contents=prompt)
        metin = (yanit.text or "").strip()
        return metin or _varsayilan_erteleme_onerisi_uret(task, profil)
    except Exception:
        logger.exception("Gemini ile erteleme önerisi üretimi başarısız oldu — kural tabanlı öneriye dönülüyor.")
        return _varsayilan_erteleme_onerisi_uret(task, profil)
