"""task_service için birim testleri."""

from datetime import date, datetime, timedelta

import pytest

from core.models import Task, User
from core.services import task_service
from core.services.task_service import (
    complete_task,
    create_task,
    delete_task,
    gecikmis_gorevleri_listele,
    havuzdaki_gorevleri_listele,
    list_tasks,
    update_task,
)


def test_gorev_olusturma(test_db, test_user_id):
    task = create_task(test_user_id, "Alışveriş yap", priority=2)

    assert task.id is not None
    assert task.user_id == test_user_id
    assert task.title == "Alışveriş yap"
    assert task.priority == 2
    assert task.done is False


def test_bos_baslik_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(test_user_id, "   ")


def test_gecersiz_oncelik_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(test_user_id, "Geçerli başlık", priority=5)


def test_gorev_tamamlama(test_db, test_user_id):
    task = create_task(test_user_id, "Bitecek görev")

    guncel = complete_task(test_user_id, task.id)

    assert guncel.done is True
    assert guncel.completed_at is not None


def test_liste_oncelige_gore_siralanir(test_db, test_user_id):
    create_task(test_user_id, "Düşük", priority=1)
    create_task(test_user_id, "Yüksek", priority=3)
    create_task(test_user_id, "Orta", priority=2)

    gorevler = list_tasks(test_user_id)

    oncelikler = [g.priority for g in gorevler]
    assert oncelikler == [3, 2, 1]


def test_gecersiz_sure_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(test_user_id, "Görev", duration_minutes=0)


def test_gorev_gune_gore_filtrelenir(test_db, test_user_id):
    bugun = date.today()
    yarin = bugun + timedelta(days=1)
    create_task(test_user_id, "Bugünkü", due_date=bugun)
    create_task(test_user_id, "Yarınki", due_date=yarin)

    gorevler = list_tasks(test_user_id, due_date=bugun)

    assert [g.title for g in gorevler] == ["Bugünkü"]


def test_baska_kullanicinin_gorevini_goremez(test_db, test_user_id):
    with test_db() as session:
        diger = User(username="diger_kullanici", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    create_task(diger_id, "Diğer kullanıcının görevi")

    assert list_tasks(test_user_id) == []


def test_baska_kullanicinin_gorevi_tamamlanamaz(test_db, test_user_id):
    with test_db() as session:
        diger = User(username="diger_kullanici2", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    diger_gorev = create_task(diger_id, "Diğer kullanıcının görevi")

    with pytest.raises(ValueError):
        complete_task(test_user_id, diger_gorev.id)
    with pytest.raises(ValueError):
        delete_task(test_user_id, diger_gorev.id)


def test_ertelenmemis_gorev_erteleme_sayaci_artmaz(test_db, test_user_id):
    yarin = date.today() + timedelta(days=1)
    task = create_task(test_user_id, "Görev", due_date=yarin)

    guncel = update_task(test_user_id, task.id, task.title, task.description, task.priority,
                          due_date=yarin + timedelta(days=1))

    assert guncel.postponement_count == 0


def test_gecikmis_gorev_ileri_tarihe_ertelenince_sayac_artar(test_db, test_user_id):
    gecmis = date.today() - timedelta(days=5)
    task = create_task(test_user_id, "Gecikmiş görev", due_date=gecmis)

    # Hâlâ gecikmiş bir tarihe itiliyor (today-5 -> today-2): yine de bir erteleme.
    guncel = update_task(test_user_id, task.id, task.title, task.description, task.priority,
                          due_date=gecmis + timedelta(days=3))
    assert guncel.postponement_count == 1

    # Şimdi geleceğe itiliyor: eski tarih hâlâ gecikmiş olduğu için yine sayılır.
    tekrar = update_task(test_user_id, guncel.id, guncel.title, guncel.description, guncel.priority,
                          due_date=date.today() + timedelta(days=1))
    assert tekrar.postponement_count == 2


def test_gecikmis_gorev_erken_tarihe_cekilirse_sayac_artmaz(test_db, test_user_id):
    gecmis = date.today() - timedelta(days=3)
    task = create_task(test_user_id, "Görev", due_date=gecmis)

    guncel = update_task(test_user_id, task.id, task.title, task.description, task.priority,
                          due_date=gecmis - timedelta(days=1))

    assert guncel.postponement_count == 0


def test_due_date_yoksa_sayac_artmaz(test_db, test_user_id):
    task = create_task(test_user_id, "Görev")

    guncel = update_task(test_user_id, task.id, task.title, task.description, task.priority, due_date=date.today())

    assert guncel.postponement_count == 0


def test_tamamlanmis_gecikmis_gorev_ertelenince_sayac_artmaz(test_db, test_user_id):
    gecmis = date.today() - timedelta(days=3)
    task = create_task(test_user_id, "Görev", due_date=gecmis)
    complete_task(test_user_id, task.id)

    guncel = update_task(test_user_id, task.id, task.title, task.description, task.priority,
                          due_date=date.today() + timedelta(days=1))

    assert guncel.postponement_count == 0


def test_gecikmis_gorevler_listelenir(test_db, test_user_id):
    bugun = date.today()
    gecmis = bugun - timedelta(days=2)
    create_task(test_user_id, "Gecikmiş", due_date=gecmis)

    gecikmisler = gecikmis_gorevleri_listele(test_user_id, bugun)

    assert [g.title for g in gecikmisler] == ["Gecikmiş"]


def test_tamamlanmis_gecikmis_gorev_listelenmez(test_db, test_user_id):
    bugun = date.today()
    gecmis = bugun - timedelta(days=2)
    task = create_task(test_user_id, "Tamamlanmış", due_date=gecmis)
    complete_task(test_user_id, task.id)

    assert gecikmis_gorevleri_listele(test_user_id, bugun) == []


def test_etkinlik_satiri_gorev_listesine_karismaz(test_db, test_user_id):
    from core.models import Task

    create_task(test_user_id, "Gerçek görev")
    with test_db() as session:
        session.add(Task(user_id=test_user_id, tur="etkinlik", title="Toplantı", start="", end="", updated=""))
        session.commit()

    gorevler = list_tasks(test_user_id)
    etkinlikler = list_tasks(test_user_id, tur="etkinlik")

    assert [g.title for g in gorevler] == ["Gerçek görev"]
    assert [e.title for e in etkinlikler] == ["Toplantı"]


def test_bugunku_ve_gelecek_gorevler_gecikmis_sayilmaz(test_db, test_user_id):
    bugun = date.today()
    create_task(test_user_id, "Bugünkü", due_date=bugun)
    create_task(test_user_id, "Gelecek", due_date=bugun + timedelta(days=1))
    create_task(test_user_id, "Tarihsiz")

    assert gecikmis_gorevleri_listele(test_user_id, bugun) == []


def test_en_erken_baslangic_kaydedilir(test_db, test_user_id):
    task = create_task(
        test_user_id, "Görev", due_date=date(2026, 8, 10), en_erken_baslangic=date(2026, 8, 5),
    )

    assert task.en_erken_baslangic == date(2026, 8, 5)


def test_due_date_en_erken_baslangictan_once_ise_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(
            test_user_id, "Görev", due_date=date(2026, 8, 1), en_erken_baslangic=date(2026, 8, 5),
        )


def test_guncellemede_en_erken_baslangic_ihlali_hata_verir(test_db, test_user_id):
    task = create_task(test_user_id, "Görev", due_date=date(2026, 8, 10))

    with pytest.raises(ValueError):
        update_task(
            test_user_id, task.id, task.title, task.description, task.priority,
            due_date=date(2026, 8, 1), en_erken_baslangic=date(2026, 8, 5),
        )


def test_konum_ve_link_kaydedilir(test_db, test_user_id):
    task = create_task(test_user_id, "Toplantı", konum="Ofis", link="https://meet.example.com")

    assert task.konum == "Ofis"
    assert task.link == "https://meet.example.com"

    guncel = update_task(
        test_user_id, task.id, task.title, task.description, task.priority,
        konum="Ev", link="https://zoom.example.com",
    )

    assert guncel.konum == "Ev"
    assert guncel.link == "https://zoom.example.com"


def test_gecersiz_teslim_tipi_hata_verir(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(test_user_id, "Görev", teslim_tipi="belirsiz")


def test_kesin_teslimde_bitis_zorunlu(test_db, test_user_id):
    with pytest.raises(ValueError):
        create_task(test_user_id, "Görev", teslim_tipi="kesin")


def test_kesin_teslim_due_date_kesin_bitisten_turetilir(test_db, test_user_id):
    bitis = datetime(2026, 8, 1, 14, 30)

    task = create_task(test_user_id, "Kesin görev", teslim_tipi="kesin", kesin_bitis=bitis)

    assert task.teslim_tipi == "kesin"
    assert task.kesin_bitis == bitis
    assert task.due_date == bitis.date()


def test_esnek_teslimde_kesin_bitis_yoksayilir(test_db, test_user_id):
    task = create_task(
        test_user_id, "Esnek görev", teslim_tipi="esnek", kesin_bitis=datetime(2026, 8, 1, 14, 30)
    )

    assert task.teslim_tipi == "esnek"
    assert task.kesin_bitis is None


def test_kesin_gorev_ileri_ertelenince_sayac_artar(test_db, test_user_id):
    ilk_bitis = datetime(2026, 8, 1, 14, 30)
    task = create_task(test_user_id, "Kesin görev", teslim_tipi="kesin", kesin_bitis=ilk_bitis)

    guncel = update_task(
        test_user_id, task.id, task.title, task.description, task.priority,
        teslim_tipi="kesin", kesin_bitis=ilk_bitis + timedelta(days=1),
    )

    assert guncel.postponement_count == 1


def test_kesin_gorev_erkene_alinirsa_sayac_artmaz(test_db, test_user_id):
    ilk_bitis = datetime(2026, 8, 1, 14, 30)
    task = create_task(test_user_id, "Kesin görev", teslim_tipi="kesin", kesin_bitis=ilk_bitis)

    guncel = update_task(
        test_user_id, task.id, task.title, task.description, task.priority,
        teslim_tipi="kesin", kesin_bitis=ilk_bitis - timedelta(hours=1),
    )

    assert guncel.postponement_count == 0


def test_havuzdaki_gorevleri_listele_tarihsiz_gorevi_dondurur(test_db, test_user_id):
    havuz_gorevi = create_task(test_user_id, "Havuz görevi")
    create_task(test_user_id, "Tarihli görev", due_date=date(2026, 8, 1))

    havuz = havuzdaki_gorevleri_listele(test_user_id)

    assert [t.id for t in havuz] == [havuz_gorevi.id]


def test_havuzdaki_gorevleri_listele_tamamlanani_disarida_birakir(test_db, test_user_id):
    havuz_gorevi = create_task(test_user_id, "Tamamlanacak havuz görevi")
    complete_task(test_user_id, havuz_gorevi.id)

    assert havuzdaki_gorevleri_listele(test_user_id) == []


def test_havuzdaki_gorevleri_listele_etkinligi_disarida_birakir(test_db, test_user_id):
    with task_service.SessionLocal() as session:
        session.add(Task(user_id=test_user_id, tur="etkinlik", title="Toplantı", start="", end="", updated=""))
        session.commit()

    assert havuzdaki_gorevleri_listele(test_user_id) == []
