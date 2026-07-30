"""rutin_service için birim testleri."""

from datetime import date, time, timedelta

import pytest

from core.models import Task
from core.services.rutin_service import (
    ROUTIN_MIN_ORNEK,
    create_rutin,
    delete_rutin,
    haftalik_rutinleri_uret,
    list_rutinler,
    rutin_erteleme_onerilerini_uret,
    update_rutin,
)


def test_rutin_olusturma(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [2, 0, 0], time(18, 0), sure_dakika=45, oncelik=2)

    assert rutin.id is not None
    assert rutin.baslik == "Spor"
    assert rutin.gunler == [0, 2]  # sıralı ve tekrarsız
    assert rutin.saat == time(18, 0)
    assert rutin.sure_dakika == 45
    assert rutin.aktif is True


def test_bos_baslik_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_rutin(test_user_id, "   ", [0], time(18, 0))


def test_gun_secilmezse_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_rutin(test_user_id, "Spor", [], time(18, 0))


def test_gecersiz_gun_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_rutin(test_user_id, "Spor", [7], time(18, 0))


def test_gecersiz_sure_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_rutin(test_user_id, "Spor", [0], time(18, 0), sure_dakika=0)


def test_gecersiz_oncelik_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_rutin(test_user_id, "Spor", [0], time(18, 0), oncelik=5)


def test_rutin_guncelleme(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))

    guncel = update_rutin(
        test_user_id, rutin.id, "Yüzme", [1, 3], time(19, 30), sure_dakika=60, oncelik=3, aktif=False
    )

    assert guncel.baslik == "Yüzme"
    assert guncel.gunler == [1, 3]
    assert guncel.saat == time(19, 30)
    assert guncel.aktif is False


def test_rutin_silme(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))

    delete_rutin(test_user_id, rutin.id)

    assert list_rutinler(test_user_id) == []


def test_baska_kullanicinin_rutinini_goremez(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_rutin", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    create_rutin(diger_id, "Diğerinin rutini", [0], time(18, 0))

    assert list_rutinler(test_user_id) == []


def test_haftalik_rutinleri_uret_dogru_gunlere_uretir(test_db, test_user_id):
    # 2026-07-06 Pazartesi. Rutin Pazartesi(0) ve Çarşamba(2) günleri için.
    rutin = create_rutin(test_user_id, "Spor", [0, 2], time(18, 0), sure_dakika=45, oncelik=2)

    uretilen = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))

    assert uretilen == 2
    with test_db() as session:
        gorevler = session.query(Task).filter(Task.rutin_id == rutin.id).order_by(Task.due_date).all()
    assert [g.due_date for g in gorevler] == [date(2026, 7, 6), date(2026, 7, 8)]
    assert all(g.sabit_saat == time(18, 0) for g in gorevler)
    assert all(g.duration_minutes == 45 for g in gorevler)
    assert all(g.tur == "gorev" for g in gorevler)


def test_haftalik_rutinleri_uret_idempotent(test_db, test_user_id):
    create_rutin(test_user_id, "Spor", [0], time(18, 0))

    ilk = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))
    ikinci = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))

    assert ilk == 1
    assert ikinci == 0


def test_pasif_rutin_materyalize_edilmez(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))
    update_rutin(test_user_id, rutin.id, "Spor", [0], time(18, 0), sure_dakika=30, oncelik=2, aktif=False)

    uretilen = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))

    assert uretilen == 0


def test_farkli_hafta_ayri_uretilir(test_db, test_user_id):
    create_rutin(test_user_id, "Spor", [0], time(18, 0))

    bu_hafta = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))
    gelecek_hafta = haftalik_rutinleri_uret(test_user_id, date(2026, 7, 13))

    assert bu_hafta == 1
    assert gelecek_hafta == 1


def _rutin_gorevi_ekle(test_db, user_id, rutin_id, gun, postponement_count):
    with test_db() as session:
        session.add(Task(
            user_id=user_id, title="Spor", rutin_id=rutin_id, tur="gorev",
            due_date=gun, duration_minutes=30, postponement_count=postponement_count,
        ))
        session.commit()


def test_esik_altinda_rutin_onerisi_uretilmez(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))
    for i in range(4):
        _rutin_gorevi_ekle(test_db, test_user_id, rutin.id, date(2026, 7, 6) + timedelta(days=7 * i), 0)

    assert rutin_erteleme_onerilerini_uret(test_user_id) == []


def test_esik_ustunde_rutin_onerisi_uretilir(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))
    for i in range(4):
        postponement = 1 if i < 3 else 0
        _rutin_gorevi_ekle(test_db, test_user_id, rutin.id, date(2026, 7, 6) + timedelta(days=7 * i), postponement)

    oneriler = rutin_erteleme_onerilerini_uret(test_user_id)

    assert any("Spor" in o for o in oneriler)


def test_minimum_ornek_altinda_oneri_uretilmez(test_db, test_user_id):
    rutin = create_rutin(test_user_id, "Spor", [0], time(18, 0))
    assert ROUTIN_MIN_ORNEK >= 2
    for i in range(ROUTIN_MIN_ORNEK - 1):
        _rutin_gorevi_ekle(test_db, test_user_id, rutin.id, date(2026, 7, 6) + timedelta(days=7 * i), 1)

    assert rutin_erteleme_onerilerini_uret(test_user_id) == []
