"""Veritabanı modelleri."""

from datetime import date, datetime, timezone
from sqlalchemy import DateTime, Integer, String
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

class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    google_id: Mapped[str] = mapped_column(String(300), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(300), default="(başlıksız)")
    description: Mapped[str] = mapped_column(String(2000), default="")
    start: Mapped[str] = mapped_column(String(50), nullable=False)
    end: Mapped[str] = mapped_column(String(50), default="")
    updated: Mapped[str] = mapped_column(String(50), default="")
    
