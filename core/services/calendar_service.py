"""Google Calendar bağlantısı ve etkinlik işlemleri"""

from datetime import datetime, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = Path("credentials.json")
TOKEN_FILE = Path("token.json")

def get_credentials() -> Credentials:
    """Geçerli bir erişim jetonu döndürür; gerekirse tarayıcıda giriş başlatır."""
    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    elif not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)

    TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds

def fetch_events(limit: int = 50) -> list[dict]:
    """Birincil takvimden yaklaşan etkinlikleri ham sözlükler olarak çeker."""
    service = build("calendar", "v3", credentials=get_credentials())
    now = datetime.now(timezone.utc).isoformat()

    result = (
        service.events()
        .list(calendarId="primary", timeMin=now, maxResults=limit, singleEvents=True,
              orderBy="startTime")
        .execute()
    )

    events = []
    for item in result.get("items", []):
        events.append({
            "google_id": item["id"],
            "title": item.get["summary", "(başlıksız)"],
            "description": item.get["description", ""],
            "start": item["start"].get("dateTime", item["end"].get("date","")),
            "updated": item.get("updated", ""),
        })

    return events
