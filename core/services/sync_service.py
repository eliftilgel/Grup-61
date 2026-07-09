"""Google Calendar ile yerel veritabanı arasındaki senkronizasyon."""

from core.database import SessionLocal
from core.models import CalendarEvent


def upsert_events(events: list[dict]) -> dict:
    """Etkinlikleri veritabanıyla eşitler; özet sayaçları döner.

    Kural: Google'dan gelen liste gerçeğin kaynağıdır (source of truth).
    Gelen yeni ise eklenir, değişmişse güncellenir, artık gelmeyen silinir.
    """
    sayac = {"eklendi": 0, "guncellendi": 0, "silindi": 0}
    gelen_idler = {e["google_id"] for e in events}

    with SessionLocal() as session:
        for e in events:
            kayit = (
                session.query(CalendarEvent)
                .filter(CalendarEvent.google_id == e["google_id"])
                .one_or_none()
            )
            if kayit is None:
                session.add(CalendarEvent(**e))
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
            .filter(CalendarEvent.google_id.not_in(gelen_idler))
            .all()
        )
        for kayit in silinecekler:
            session.delete(kayit)
            sayac["silindi"] += 1

        session.commit()

    return sayac


def sync_from_google() -> dict:
    """Google'dan çek ve veritabanıyla eşitle."""
    from core.services.calendar_service import fetch_events

    return upsert_events(fetch_events())


def list_events() -> list[CalendarEvent]:
    """Yerel kopyadaki etkinlikleri başlangıç sırasına göre döner."""
    with SessionLocal() as session:
        return list(
            session.query(CalendarEvent).order_by(CalendarEvent.start)
        )

def create_event_everywhere(
    title: str, start_iso: str, end_iso: str, description: str = ""
) -> None:
    """Etkinliği önce Google'da oluşturur, sonra yerel kopyaya işler."""
    from core.services.calendar_service import create_event

    google_kayit = create_event(title, start_iso, end_iso, description)

    with SessionLocal() as session:
        session.add(CalendarEvent(
            google_id=google_kayit["id"],
            title=title,
            description=description,
            start=start_iso,
            end=end_iso,
            updated=google_kayit.get("updated", ""),
        ))
        session.commit()