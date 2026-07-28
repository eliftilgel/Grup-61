"""user_service için birim testleri."""

import pytest

from core.services.user_service import (
    authenticate,
    create_user,
    delete_user,
    get_user,
    list_users,
    set_admin,
    sifre_sifirla,
)


def test_kullanici_olusturma(test_db):
    user = create_user("ayse", "gizli123")

    assert user.id is not None
    assert user.username == "ayse"
    assert user.is_admin is False
    assert user.password_hash != "gizli123"


def test_ayni_kullanici_adi_reddedilir(test_db):
    create_user("ayse", "gizli123")

    with pytest.raises(ValueError):
        create_user("ayse", "baska1234")


def test_bos_kullanici_adi_reddedilir(test_db):
    with pytest.raises(ValueError):
        create_user("   ", "gizli123")


def test_kisa_parola_reddedilir(test_db):
    with pytest.raises(ValueError):
        create_user("mehmet", "abc")


def test_dogru_bilgiyle_giris_basarili(test_db):
    create_user("ayse", "gizli123")

    user = authenticate("ayse", "gizli123")

    assert user is not None
    assert user.username == "ayse"


def test_yanlis_sifreyle_giris_basarisiz(test_db):
    create_user("ayse", "gizli123")

    assert authenticate("ayse", "yanlis-sifre") is None


def test_olmayan_kullaniciyla_giris_basarisiz(test_db):
    assert authenticate("yok_boyle_biri", "herhangi") is None


def test_list_users_kayit_sirasina_gore_doner(test_db):
    create_user("birinci", "gizli123")
    create_user("ikinci", "gizli123")

    kullanicilar = list_users()

    assert [u.username for u in kullanicilar] == ["birinci", "ikinci"]


def test_get_user(test_db):
    olusturulan = create_user("ayse", "gizli123")

    bulunan = get_user(olusturulan.id)

    assert bulunan.username == "ayse"
    assert get_user(999999) is None


def test_delete_user(test_db):
    user = create_user("silinecek", "gizli123")

    delete_user(user.id)

    assert get_user(user.id) is None
    with pytest.raises(ValueError):
        delete_user(user.id)


def test_son_admin_silinemez(test_db):
    tek_admin = create_user("tek_admin", "gizli123")
    set_admin(tek_admin.id, True)

    with pytest.raises(ValueError):
        delete_user(tek_admin.id)

    assert get_user(tek_admin.id) is not None


def test_birden_fazla_admin_varsa_silinebilir(test_db):
    admin1 = create_user("admin_bir", "gizli123")
    admin2 = create_user("admin_iki", "gizli123")
    set_admin(admin1.id, True)
    set_admin(admin2.id, True)

    delete_user(admin1.id)

    assert get_user(admin1.id) is None
    assert get_user(admin2.id) is not None


def test_set_admin(test_db):
    user = create_user("normal", "gizli123")
    assert user.is_admin is False

    guncel = set_admin(user.id, True)
    assert guncel.is_admin is True

    guncel2 = set_admin(user.id, False)
    assert guncel2.is_admin is False


def test_sifre_sifirla(test_db):
    user = create_user("ayse", "eski-sifre")

    sifre_sifirla(user.id, "yeni-sifre123")

    assert authenticate("ayse", "eski-sifre") is None
    assert authenticate("ayse", "yeni-sifre123") is not None


def test_sifre_sifirla_kisa_parolayi_reddeder(test_db):
    user = create_user("ayse", "eski-sifre")

    with pytest.raises(ValueError):
        sifre_sifirla(user.id, "ab")


def test_delete_user_kullanicinin_verisini_de_siler(test_db):
    from core.models import Task
    from core.services.task_service import create_task

    user = create_user("silinecek2", "gizli123")
    create_task(user.id, "Görev")

    delete_user(user.id)

    with test_db() as session:
        kalan = session.query(Task).filter(Task.user_id == user.id).all()
        assert kalan == []
