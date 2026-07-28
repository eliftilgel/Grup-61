"""Google Calendar ile yerel veritabanı arasındaki senkronizasyon.

Google hesabı tüm kullanıcılar arasında paylaşılan tek hesap (kullanıcı
başına OAuth henüz yok) — yerel `CalendarEvent` kayıtları `user_id` ile
kullanıcıya özel tutulur, `google_id` artık kullanıcı başına benzersizdir.
"""

import logging

from core.database import SessionLocal
from core.models import CalendarEvent

logger = logging.getLogger(__name__)


def upsert_events(user_id: int, events: list[dict]) -> dict:
    """Etkinlikleri kullanıcının yerel kopyasıyla eşitler; özet sayaçları döner.

    Kural: Google'dan gelen liste gerçeğin kaynağıdır (source of truth).
    Gelen yeni ise eklenir, değişmişse güncellenir, artık gelmeyen silinir.
    """
    sayac = {"eklendi": 0, "guncellendi": 0, "silindi": 0}
    gelen_idler = {e["google_id"] for e in events}

    with SessionLocal() as session:
        for e in events:
            kayit = (
                session.query(CalendarEvent)
                .filter(CalendarEvent.user_id == user_id, CalendarEvent.google_id == e["google_id"])
                .one_or_none()
            )
            if kayit is None:
                session.add(CalendarEvent(user_id=user_id, **e))
                sayac["eklendi"] += 1
            elif kayit.updated != e["updated"]:
                kayit.title = e["title"]
                kayit.description = e["description"]
                kayit.start = e["start"]
                kayit.end = e["end"]
                kayit.updated = e["updated"]
                sayac["guncellendi"] += 1

        silinecekler = (
            session.query(CalendarEvent)
            .filter(CalendarEvent.user_id == user_id, CalendarEvent.google_id.not_in(gelen_idler))
            .all()
        )
        for kayit in silinecekler:
            session.delete(kayit)
            sayac["silindi"] += 1

        session.commit()

    return sayac


def sync_from_google(user_id: int) -> dict:
    """Google'dan çek ve kullanıcının yerel kopyasıyla eşitle."""
    from core.services.calendar_service import fetch_events

    try:
        sayac = upsert_events(user_id, fetch_events())
    except Exception:
        logger.exception("Google Takvim senkronu başarısız oldu")
        raise
    logger.info(
        "Google Takvim senkronu tamamlandı: %(eklendi)s eklendi, "
        "%(guncellendi)s güncellendi, %(silindi)s silindi", sayac
    )
    return sayac


def list_events(user_id: int) -> list[CalendarEvent]:
    """Kullanıcının yerel kopyasındaki etkinlikleri başlangıç sırasına göre döner."""
    with SessionLocal() as session:
        return list(
            session.query(CalendarEvent)
            .filter(CalendarEvent.user_id == user_id)
            .order_by(CalendarEvent.start)
        )

def create_event_everywhere(
    user_id: int, title: str, start_iso: str, end_iso: str, description: str = ""
) -> None:
    """Etkinliği önce Google'da oluşturur, sonra kullanıcının yerel kopyasına işler."""
    from core.services.calendar_service import create_event

    try:
        google_kayit = create_event(title, start_iso, end_iso, description)
    except Exception:
        logger.exception("Google Takvim'de etkinlik oluşturulamadı: %s", title)
        raise

    with SessionLocal() as session:
        session.add(CalendarEvent(
            user_id=user_id,
            google_id=google_kayit["id"],
            title=title,
            description=description,
            start=start_iso,
            end=end_iso,
            updated=google_kayit.get("updated", ""),
        ))
        session.commit()
    logger.info("Etkinlik oluşturuldu ve yerel kopyaya işlendi: %s", title)
