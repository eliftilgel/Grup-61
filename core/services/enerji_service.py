"""Kullanıcının gün bazlı enerji/ruh hali seviyesi — plan oluşturma sıralamasını etkiler
(bkz. planning_service.plan_olustur)."""

from datetime import date

from core.database import SessionLocal
from core.models import GunlukEnerji

GECERLI_SEVIYELER = ("dusuk", "orta", "yuksek")


def set_enerji_seviyesi(user_id: int, gun: date, seviye: str) -> GunlukEnerji:
    """O gün için enerji seviyesini kaydeder; zaten kayıt varsa üzerine yazar (upsert)."""
    if seviye not in GECERLI_SEVIYELER:
        raise ValueError("Enerji seviyesi 'dusuk', 'orta' veya 'yuksek' olmalı")

    with SessionLocal() as session:
        kayit = (
            session.query(GunlukEnerji)
            .filter(GunlukEnerji.user_id == user_id, GunlukEnerji.gun == gun)
            .one_or_none()
        )
        if kayit is None:
            kayit = GunlukEnerji(user_id=user_id, gun=gun, seviye=seviye)
            session.add(kayit)
        else:
            kayit.seviye = seviye
        session.commit()
        session.refresh(kayit)
        return kayit


def get_enerji_seviyesi(user_id: int, gun: date) -> str | None:
    """O gün için kaydedilmiş enerji seviyesini döner; yoksa None."""
    with SessionLocal() as session:
        kayit = (
            session.query(GunlukEnerji)
            .filter(GunlukEnerji.user_id == user_id, GunlukEnerji.gun == gun)
            .one_or_none()
        )
        return kayit.seviye if kayit is not None else None
