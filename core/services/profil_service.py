"""Kullanıcı profili/ayarları — her kullanıcının tam olarak bir profili olur (user_id ile)."""

from datetime import time

from core.database import SessionLocal
from core.models import Profil


def get_or_create(user_id: int) -> Profil:
    """Kullanıcının profilini döner; yoksa varsayılan değerlerle oluşturur."""
    with SessionLocal() as session:
        profil = session.query(Profil).filter(Profil.user_id == user_id).one_or_none()
        if profil is None:
            profil = Profil(user_id=user_id)
            session.add(profil)
            session.commit()
            session.refresh(profil)
        return profil


def save(
    user_id: int,
    ad_soyad: str,
    e_posta: str,
    verimli_baslangic: time,
    verimli_bitis: time,
    uyku_baslangic: time,
    uyku_bitis: time,
    gunluk_hedef: int,
) -> Profil:
    """Profil bilgilerini doğrular ve kaydeder."""
    if not ad_soyad.strip():
        raise ValueError("Ad soyad boş olamaz")
    if verimli_bitis <= verimli_baslangic:
        raise ValueError("Verimli bitiş saati başlangıçtan sonra olmalı")
    if gunluk_hedef < 1:
        raise ValueError("Günlük hedef en az 1 olmalı")

    with SessionLocal() as session:
        profil = session.query(Profil).filter(Profil.user_id == user_id).one_or_none()
        if profil is None:
            profil = Profil(user_id=user_id)
        profil.ad_soyad = ad_soyad.strip()
        profil.e_posta = e_posta.strip()
        profil.verimli_baslangic = verimli_baslangic
        profil.verimli_bitis = verimli_bitis
        profil.uyku_baslangic = uyku_baslangic
        profil.uyku_bitis = uyku_bitis
        profil.gunluk_hedef = gunluk_hedef
        session.add(profil)
        session.commit()
        session.refresh(profil)
        return profil
