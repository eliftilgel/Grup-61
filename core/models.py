"""Veritabanı modelleri."""

from datetime import date, datetime, time, timezone
from sqlalchemy import JSON, DateTime, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    done: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    postponement_count: Mapped[int] = mapped_column(Integer, default=0)

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_id: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="(başlıksız)")
    description: Mapped[str] = mapped_column(String(2000), default="")
    start: Mapped[str] = mapped_column(String(50), nullable=False)
    end: Mapped[str] = mapped_column(String(50), default="")
    updated: Mapped[str] = mapped_column(String(50), default="")


class Profil(Base):
    """Tek kullanıcılı yerel uygulama için tek satırlık ayar profili (id=1)."""

    __tablename__ = "profil"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ad_soyad: Mapped[str] = mapped_column(String(200), default="")
    e_posta: Mapped[str] = mapped_column(String(200), default="")
    verimli_baslangic: Mapped[time] = mapped_column(Time, default=lambda: time(7, 0))
    verimli_bitis: Mapped[time] = mapped_column(Time, default=lambda: time(13, 0))
    uyku_baslangic: Mapped[time] = mapped_column(Time, default=lambda: time(23, 0))
    uyku_bitis: Mapped[time] = mapped_column(Time, default=lambda: time(7, 0))
    gunluk_hedef: Mapped[int] = mapped_column(Integer, default=5)


class PlanKaydi(Base):
    """Bir günlük plan üretiminin geçmiş kaydı (yeniden üretim = yeni satır)."""

    __tablename__ = "plan_kayitlari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    gun: Mapped[date] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    dilimler: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    toplam_is_dakika: Mapped[int] = mapped_column(Integer, default=0)
    bos_zaman_dakika: Mapped[int] = mapped_column(Integer, default=0)
    genel_tavsiye: Mapped[str] = mapped_column(String(1000), default="")
