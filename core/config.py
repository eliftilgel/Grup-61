"""Uygulama ayarları — .env dosyasından okunur, tek doğruluk kaynağı."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8")

    database_url: str = f"sqlite:///{BASE_DIR / 'planner.db'}"
    sqlalchemy_echo: bool = False

    google_credentials_file: Path = BASE_DIR / "credentials.json"
    google_token_file: Path = BASE_DIR / "token.json"
    google_calendar_scopes: list[str] = ["https://www.googleapis.com/auth/calendar.events"]

    # ai_advisor.py: Gemini API anahtarı — boşsa AI zenginleştirme sessizce devre dışı kalır.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"


settings = Settings()
