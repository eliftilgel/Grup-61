"""Tek kullanıcılı parola doğrulama — Streamlit'ten bağımsız, test edilebilir."""

import bcrypt


def sifre_dogrula(hash: str, girilen: str) -> bool:
    """Girilen parolanın saklanan bcrypt hash'iyle eşleşip eşleşmediğini döner."""
    try:
        return bcrypt.checkpw(girilen.encode("utf-8"), hash.encode("utf-8"))
    except ValueError:
        return False
