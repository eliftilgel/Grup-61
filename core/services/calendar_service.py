"""Google Calendar bağlantısı ve etkinlik işlemleri."""

from datetime import datetime, timezone

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from core.config import settings


def _get_credentials() -> Credentials:
    """Geçerli bir erişim jetonu döndürür; gerekirse tarayıcıda giriş başlatır."""
    creds = None
    if settings.google_token_file.exists():
        creds = Credentials.from_authorized_user_file(
            settings.google_token_file, settings.google_calendar_scopes
        )

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.google_credentials_file, settings.google_calendar_scopes
        )
        creds = flow.run_local_server(port=0)

    settings.google_token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds


def fetch_events(limit: int = 50) -> list[dict]:
    """Birincil takvimden yaklaşan etkinlikleri ham sözlükler olarak çeker."""
    service = build("calendar", "v3", credentials=_get_credentials())
    now = datetime.now(timezone.utc).isoformat()

    result = (
        service.events()
        .list(calendarId="primary", timeMin=now, maxResults=limit,
              singleEvents=True, orderBy="startTime")
        .execute()
    )

    events = []
    for item in result.get("items", []):
        events.append({
            "google_id": item["id"],
            "title": item.get("summary", "(başlıksız)"),
            "description": item.get("description", ""),
            "start": item["start"].get("dateTime", item["start"].get("date", "")),
            "end": item["end"].get("dateTime", item["end"].get("date", "")),
            "updated": item.get("updated", ""),
        })
    return events


def create_event(title: str, start_iso: str, end_iso: str, description: str = "") -> dict:
    """Google Takvim'de etkinlik oluşturur; Google'ın döndürdüğü kaydı verir."""
    service = build("calendar", "v3", credentials=_get_credentials())
    govde = {
        "summary": title,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    return service.events().insert(calendarId="primary", body=govde).execute()


def delete_event(google_id: str) -> None:
    """Google Takvim'den etkinliği siler."""
    service = build("calendar", "v3", credentials=_get_credentials())
    service.events().delete(calendarId="primary", eventId=google_id).execute()