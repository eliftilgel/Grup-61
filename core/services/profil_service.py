"""Kullanıcı profili/ayarları — tek satırlık (id=1) yerel profil, çoklu-kullanıcı auth değil."""

from datetime import time

from core.database import SessionLocal
from core.models import Profil

PROFIL_ID = 1


def get_or_create() -> Profil:
    """Tek profil satırını döner; yoksa varsayılan değerlerle oluşturur."""
    with SessionLocal() as session:
        profil = session.get(Profil, PROFIL_ID)
        if profil is None:
            profil = Profil(id=PROFIL_ID)
            session.add(profil)
            session.commit()
            session.refresh(profil)
        return profil


def save(
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
        profil = session.get(Profil, PROFIL_ID)
        if profil is None:
            profil = Profil(id=PROFIL_ID)
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
