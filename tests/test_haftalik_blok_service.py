"""haftalik_blok_service için birim testleri."""

from datetime import time

import pytest

from core.services.haftalik_blok_service import create_blok, delete_blok, list_bloklar


def test_blok_olusturma(test_db, test_user_id):
    blok = create_blok(test_user_id, "sabit_kapali", 3, time(9, 0), time(12, 0), etiket="Ders")

    assert blok.id is not None
    assert blok.tur == "sabit_kapali"
    assert blok.gun == 3
    assert blok.baslangic == time(9, 0)
    assert blok.bitis == time(12, 0)
    assert blok.etiket == "Ders"


def test_gecersiz_tur_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_blok(test_user_id, "gecersiz", 0, time(9, 0), time(12, 0))


def test_gecersiz_gun_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_blok(test_user_id, "sabit_kapali", 7, time(9, 0), time(12, 0))


def test_bitis_baslangictan_once_ise_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_blok(test_user_id, "sabit_kapali", 0, time(12, 0), time(9, 0))


def test_list_bloklar_gune_gore_filtreler(test_db, test_user_id):
    create_blok(test_user_id, "sabit_kapali", 0, time(9, 0), time(12, 0), etiket="Ders")
    create_blok(test_user_id, "serbest", 2, time(18, 0), time(19, 0), etiket="Hobi")

    pazartesi_bloklari = list_bloklar(test_user_id, gun=0)
    tum_bloklar = list_bloklar(test_user_id)

    assert [b.etiket for b in pazartesi_bloklari] == ["Ders"]
    assert len(tum_bloklar) == 2


def test_blok_silme(test_db, test_user_id):
    blok = create_blok(test_user_id, "sabit_kapali", 0, time(9, 0), time(12, 0))

    delete_blok(test_user_id, blok.id)

    assert list_bloklar(test_user_id) == []


def test_baska_kullanicinin_blogunu_goremez(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_blok", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    create_blok(diger_id, "sabit_kapali", 0, time(9, 0), time(12, 0))

    assert list_bloklar(test_user_id) == []


def test_baska_kullanicinin_blogunu_silemez(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_blok2", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    diger_blok = create_blok(diger_id, "sabit_kapali", 0, time(9, 0), time(12, 0))

    with pytest.raises(ValueError):
        delete_blok(test_user_id, diger_blok.id)
