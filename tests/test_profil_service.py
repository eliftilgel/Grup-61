"""profil_service için birim testleri."""

from datetime import time

import pytest

from core.services.profil_service import get_or_create, save


def test_ilk_erisimde_varsayilanlarla_olusturulur(test_db, test_user_id):
    profil = get_or_create(test_user_id)

    assert profil.user_id == test_user_id
    assert profil.gunluk_hedef == 5
    assert profil.verimli_baslangic == time(7, 0)
    assert profil.uyku_baslangic == time(23, 0)


def test_get_or_create_idempotenttir(test_db, test_user_id):
    birinci = get_or_create(test_user_id)
    ikinci = get_or_create(test_user_id)

    assert birinci.id == ikinci.id


def test_kaydetme_ve_tekrar_okuma(test_db, test_user_id):
    save(test_user_id, "Ece Gürbüz", "ece@planla.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)

    profil = get_or_create(test_user_id)

    assert profil.ad_soyad == "Ece Gürbüz"
    assert profil.e_posta == "ece@planla.app"
    assert profil.gunluk_hedef == 5


def test_bos_ad_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        save(test_user_id, "  ", "e@e.com", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)


def test_gecersiz_verimli_pencere_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        save(test_user_id, "Ad Soyad", "e@e.com", time(13, 0), time(7, 0), time(23, 0), time(7, 0), 5)


def test_gecersiz_gunluk_hedef_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        save(test_user_id, "Ad Soyad", "e@e.com", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 0)


def test_buffer_dakika_kaydedilir_ve_okunur(test_db, test_user_id):
    save(test_user_id, "Ece Gürbüz", "ece@planla.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5, 15)

    profil = get_or_create(test_user_id)

    assert profil.buffer_dakika == 15


def test_negatif_buffer_dakika_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        save(test_user_id, "Ad Soyad", "e@e.com", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5, -5)


def test_farkli_kullanicilarin_profili_ayridir(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_profil", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    save(test_user_id, "Kullanıcı Bir", "bir@planla.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)

    diger_profil = get_or_create(diger_id)
    assert diger_profil.ad_soyad == ""
