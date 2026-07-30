"""enerji_service için birim testleri."""

from datetime import date

import pytest

from core.services.enerji_service import get_enerji_seviyesi, set_enerji_seviyesi


def test_enerji_seviyesi_kaydedilir_ve_okunur(test_db, test_user_id):
    set_enerji_seviyesi(test_user_id, date(2026, 7, 6), "dusuk")

    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 6)) == "dusuk"


def test_kayit_yoksa_none_doner(test_db, test_user_id):
    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 6)) is None


def test_gecersiz_seviye_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        set_enerji_seviyesi(test_user_id, date(2026, 7, 6), "asiri_yuksek")


def test_ayni_gun_ikinci_kez_set_uzerine_yazar(test_db, test_user_id):
    set_enerji_seviyesi(test_user_id, date(2026, 7, 6), "dusuk")
    set_enerji_seviyesi(test_user_id, date(2026, 7, 6), "yuksek")

    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 6)) == "yuksek"


def test_farkli_gunler_bagimsizdir(test_db, test_user_id):
    set_enerji_seviyesi(test_user_id, date(2026, 7, 6), "dusuk")
    set_enerji_seviyesi(test_user_id, date(2026, 7, 7), "yuksek")

    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 6)) == "dusuk"
    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 7)) == "yuksek"


def test_baska_kullanicinin_enerjisini_gormez(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_enerji", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    set_enerji_seviyesi(diger_id, date(2026, 7, 6), "yuksek")

    assert get_enerji_seviyesi(test_user_id, date(2026, 7, 6)) is None
