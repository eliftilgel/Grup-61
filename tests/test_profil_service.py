"""profil_service için birim testleri."""

from datetime import time

import pytest

from core.services.profil_service import get_or_create, save


def test_ilk_erisimde_varsayilanlarla_olusturulur(test_db):
    profil = get_or_create()

    assert profil.id == 1
    assert profil.gunluk_hedef == 5
    assert profil.verimli_baslangic == time(7, 0)
    assert profil.uyku_baslangic == time(23, 0)


def test_get_or_create_idempotenttir(test_db):
    birinci = get_or_create()
    ikinci = get_or_create()

    assert birinci.id == ikinci.id


def test_kaydetme_ve_tekrar_okuma(test_db):
    save("Ece Gürbüz", "ece@flowday.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)

    profil = get_or_create()

    assert profil.ad_soyad == "Ece Gürbüz"
    assert profil.e_posta == "ece@flowday.app"
    assert profil.gunluk_hedef == 5


def test_bos_ad_hata_verir(test_db):
    with pytest.raises(ValueError):
        save("  ", "e@e.com", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)


def test_gecersiz_verimli_pencere_hata_verir(test_db):
    with pytest.raises(ValueError):
        save("Ad Soyad", "e@e.com", time(13, 0), time(7, 0), time(23, 0), time(7, 0), 5)


def test_gecersiz_gunluk_hedef_hata_verir(test_db):
    with pytest.raises(ValueError):
        save("Ad Soyad", "e@e.com", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 0)
