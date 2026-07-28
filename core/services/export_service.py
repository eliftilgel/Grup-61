"""Kullanıcı verisinin tamamının dışa aktarımı (yedekleme/taşınabilirlik).

Sadece dışa aktarma — içe aktarma/restore bu servisin kapsamında değil.
"""

from datetime import datetime, timezone

from core.database import SessionLocal
from core.models import CalendarEvent, PlanKaydi, Profil, Task


def _isoya_cevir(deger):
    if deger is None:
        return None
    if hasattr(deger, "isoformat"):
        return deger.isoformat()
    return deger


def _gorev_sozluk(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "done": task.done,
        "created_at": _isoya_cevir(task.created_at),
        "due_date": _isoya_cevir(task.due_date),
        "duration_minutes": task.duration_minutes,
        "completed_at": _isoya_cevir(task.completed_at),
        "postponement_count": task.postponement_count,
    }


def _etkinlik_sozluk(event: CalendarEvent) -> dict:
    return {
        "id": event.id,
        "google_id": event.google_id,
        "title": event.title,
        "description": event.description,
        "start": event.start,
        "end": event.end,
        "updated": event.updated,
    }


def _profil_sozluk(profil: Profil | None) -> dict | None:
    if profil is None:
        return None
    return {
        "ad_soyad": profil.ad_soyad,
        "e_posta": profil.e_posta,
        "verimli_baslangic": _isoya_cevir(profil.verimli_baslangic),
        "verimli_bitis": _isoya_cevir(profil.verimli_bitis),
        "uyku_baslangic": _isoya_cevir(profil.uyku_baslangic),
        "uyku_bitis": _isoya_cevir(profil.uyku_bitis),
        "gunluk_hedef": profil.gunluk_hedef,
    }


def _plan_kaydi_sozluk(kayit: PlanKaydi) -> dict:
    return {
        "id": kayit.id,
        "gun": _isoya_cevir(kayit.gun),
        "created_at": _isoya_cevir(kayit.created_at),
        "dilimler": kayit.dilimler,
        "toplam_is_dakika": kayit.toplam_is_dakika,
        "bos_zaman_dakika": kayit.bos_zaman_dakika,
        "genel_tavsiye": kayit.genel_tavsiye,
    }


def tum_veriyi_disa_aktar() -> dict:
    """Kullanıcının tüm verisini JSON-serileştirilebilir tek bir sözlükte döner."""
    with SessionLocal() as session:
        gorevler = session.query(Task).all()
        etkinlikler = session.query(CalendarEvent).all()
        profil = session.get(Profil, 1)
        plan_kayitlari = session.query(PlanKaydi).all()

        return {
            "disa_aktarma_tarihi": datetime.now(timezone.utc).isoformat(),
            "gorevler": [_gorev_sozluk(t) for t in gorevler],
            "takvim_etkinlikleri": [_etkinlik_sozluk(e) for e in etkinlikler],
            "profil": _profil_sozluk(profil),
            "plan_kayitlari": [_plan_kaydi_sozluk(p) for p in plan_kayitlari],
        }
