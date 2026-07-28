"""core.auth için birim testleri."""

import bcrypt

from core.auth import sifre_dogrula


def _hash_uret(sifre: str) -> str:
    return bcrypt.hashpw(sifre.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def test_dogru_sifre_kabul_edilir():
    hash_ = _hash_uret("gizli-sifre")

    assert sifre_dogrula(hash_, "gizli-sifre") is True


def test_yanlis_sifre_reddedilir():
    hash_ = _hash_uret("gizli-sifre")

    assert sifre_dogrula(hash_, "baska-sifre") is False


def test_bozuk_hash_hata_firlatmaz_reddeder():
    assert sifre_dogrula("gecersiz-hash", "herhangi-bir-sifre") is False
