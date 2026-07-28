"""Kullanıcı hesabı yönetimi — kayıt, giriş, admin işlemleri."""

from core.auth import sifre_dogrula, sifre_hashle
from core.database import SessionLocal
from core.models import User

MIN_PAROLA_UZUNLUGU = 4


def create_user(username: str, password: str) -> User:
    """Yeni kullanıcı oluşturur (her zaman is_admin=False ile)."""
    username = username.strip()
    if not username:
        raise ValueError("Kullanıcı adı boş olamaz")
    if len(password) < MIN_PAROLA_UZUNLUGU:
        raise ValueError(f"Parola en az {MIN_PAROLA_UZUNLUGU} karakter olmalı")

    with SessionLocal() as session:
        if session.query(User).filter(User.username == username).one_or_none() is not None:
            raise ValueError("Bu kullanıcı adı zaten alınmış")

        user = User(username=username, password_hash=sifre_hashle(password), is_admin=False)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def authenticate(username: str, password: str) -> User | None:
    """Kullanıcı adı/parola doğruysa User döner, değilse None."""
    with SessionLocal() as session:
        user = session.query(User).filter(User.username == username.strip()).one_or_none()
        if user is None or not sifre_dogrula(user.password_hash, password):
            return None
        return user


def list_users() -> list[User]:
    """Tüm kullanıcıları kayıt tarihine göre listeler."""
    with SessionLocal() as session:
        return list(session.query(User).order_by(User.created_at.asc()))


def get_user(user_id: int) -> User | None:
    with SessionLocal() as session:
        return session.get(User, user_id)


def delete_user(user_id: int) -> None:
    """Kullanıcıyı ve (ondelete=CASCADE sayesinde) tüm verisini siler.

    Son admin hesabının silinmesine izin vermez — aksi halde kimse admin
    paneline erişemez hale gelir.
    """
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"{user_id} numaralı kullanıcı bulunamadı.")
        if user.is_admin:
            admin_sayisi = session.query(User).filter(User.is_admin.is_(True)).count()
            if admin_sayisi <= 1:
                raise ValueError("Son admin hesabı silinemez — önce başka bir kullanıcıyı admin yap.")
        session.delete(user)
        session.commit()


def set_admin(user_id: int, is_admin: bool) -> User:
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"{user_id} numaralı kullanıcı bulunamadı.")
        user.is_admin = is_admin
        session.commit()
        session.refresh(user)
        return user


def sifre_sifirla(user_id: int, yeni_sifre: str) -> User:
    if len(yeni_sifre) < MIN_PAROLA_UZUNLUGU:
        raise ValueError(f"Parola en az {MIN_PAROLA_UZUNLUGU} karakter olmalı")
    with SessionLocal() as session:
        user = session.get(User, user_id)
        if user is None:
            raise ValueError(f"{user_id} numaralı kullanıcı bulunamadı.")
        user.password_hash = sifre_hashle(yeni_sifre)
        session.commit()
        session.refresh(user)
        return user
