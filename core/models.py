"""Veritabanı modelleri."""

from datetime import date, datetime, time, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class User(Base):
    """Uygulama kullanıcısı — çoklu kullanıcı sisteminin temeli."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Task(Base):
    """`tur` == "etkinlik" olan satırlar Google Takvim'den senkronlanan/oluşturulan etkinlikleri
    temsil eder (eskiden ayrı bir CalendarEvent tablosuydu, aynı yapıda birleştirildi).
    google_id yalnızca etkinlik satırlarında dolu olur; görev satırlarında NULL kalır — bu yüzden
    (user_id, google_id) unique constraint'i görev satırları arasında çakışma yaratmaz."""

    __tablename__ = "tasks"
    __table_args__ = (UniqueConstraint("user_id", "google_id", name="uq_tasks_user_google"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(1000), default="")
    priority: Mapped[int] = mapped_column(Integer, default=1)
    done: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    due_date: Mapped[date | None] = mapped_column(nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=30)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    postponement_count: Mapped[int] = mapped_column(Integer, default=0)
    konum: Mapped[str] = mapped_column(String(300), default="")
    link: Mapped[str] = mapped_column(String(500), default="")
    teslim_tipi: Mapped[str] = mapped_column(String(10), default="esnek")
    kesin_bitis: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    tur: Mapped[str] = mapped_column(String(10), default="gorev")
    google_id: Mapped[str | None] = mapped_column(String(300), nullable=True)
    start: Mapped[str] = mapped_column(String(50), default="")
    end: Mapped[str] = mapped_column(String(50), default="")
    updated: Mapped[str] = mapped_column(String(50), default="")
    rutin_id: Mapped[int | None] = mapped_column(ForeignKey("rutinler.id", ondelete="SET NULL"), nullable=True)
    sabit_saat: Mapped[time | None] = mapped_column(Time, nullable=True)
    en_erken_baslangic: Mapped[date | None] = mapped_column(nullable=True)


class Rutin(Base):
    """Tekrarlayan görev şablonu — her hafta `gunler`de belirtilen günlerde, `saat`te
    sabit bir görev olarak materyalize edilir (bkz. rutin_service.haftalik_rutinleri_uret)."""

    __tablename__ = "rutinler"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    baslik: Mapped[str] = mapped_column(String(200), nullable=False)
    gunler: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    saat: Mapped[time] = mapped_column(Time, nullable=False)
    sure_dakika: Mapped[int] = mapped_column(Integer, default=30)
    oncelik: Mapped[int] = mapped_column(Integer, default=2)
    aktif: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Profil(Base):
    """Kullanıcı ayar profili — her kullanıcının tam olarak bir profili olur (user_id unique)."""

    __tablename__ = "profil"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    ad_soyad: Mapped[str] = mapped_column(String(200), default="")
    e_posta: Mapped[str] = mapped_column(String(200), default="")
    verimli_baslangic: Mapped[time] = mapped_column(Time, default=lambda: time(7, 0))
    verimli_bitis: Mapped[time] = mapped_column(Time, default=lambda: time(13, 0))
    uyku_baslangic: Mapped[time] = mapped_column(Time, default=lambda: time(23, 0))
    uyku_bitis: Mapped[time] = mapped_column(Time, default=lambda: time(7, 0))
    gunluk_hedef: Mapped[int] = mapped_column(Integer, default=5)
    buffer_dakika: Mapped[int] = mapped_column(Integer, default=0)


class HaftalikBlok(Base):
    """Haftalık tekrar eden, kalıcı bir uygun-olmayan zaman bloğu (bir gün = bir satır).
    `tur`: "sabit_kapali" (ör. ders) veya "serbest" (ör. korunan kişisel zaman) — planlama
    algoritması için ikisi de aynı şekilde "meşgul" sayılır, sadece Ayarlar'da farklı
    gruplanıp gösterilirler."""

    __tablename__ = "haftalik_bloklar"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    tur: Mapped[str] = mapped_column(String(15), default="sabit_kapali")
    gun: Mapped[int] = mapped_column(Integer, nullable=False)
    baslangic: Mapped[time] = mapped_column(Time, nullable=False)
    bitis: Mapped[time] = mapped_column(Time, nullable=False)
    etiket: Mapped[str] = mapped_column(String(100), default="")


class PlanKaydi(Base):
    """Bir günlük plan üretiminin geçmiş kaydı (yeniden üretim = yeni satır)."""

    __tablename__ = "plan_kayitlari"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gun: Mapped[date] = mapped_column(nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    dilimler: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    toplam_is_dakika: Mapped[int] = mapped_column(Integer, default=0)
    bos_zaman_dakika: Mapped[int] = mapped_column(Integer, default=0)
    genel_tavsiye: Mapped[str] = mapped_column(String(1000), default="")
    enerji_seviyesi: Mapped[str | None] = mapped_column(String(10), nullable=True)
    strateji: Mapped[str | None] = mapped_column(String(20), nullable=True)


class GunlukEnerji(Base):
    """Kullanıcının belirli bir gün için seçtiği enerji/ruh hali seviyesi — plan oluşturma
    sıralamasını etkiler (bkz. planning_service.plan_olustur)."""

    __tablename__ = "gunluk_enerji"
    __table_args__ = (UniqueConstraint("user_id", "gun", name="uq_gunluk_enerji_user_gun"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    gun: Mapped[date] = mapped_column(nullable=False)
    seviye: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
