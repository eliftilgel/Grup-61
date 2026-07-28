"""task_service için birim testleri."""

from datetime import date, timedelta

import pytest

from core.services.task_service import (
    complete_task,
    create_task,
    gecikmis_gorevleri_listele,
    list_tasks,
    update_task,
)


def test_gorev_olusturma(test_db):
    task = create_task("Alışveriş yap", priority=2)

    assert task.id is not None
    assert task.title == "Alışveriş yap"
    assert task.priority == 2
    assert task.done is False


def test_bos_baslik_hata_verir(test_db):
    with pytest.raises(ValueError):
        create_task("   ")


def test_gecersiz_oncelik_hata_verir(test_db):
    with pytest.raises(ValueError):
        create_task("Geçerli başlık", priority=5)


def test_gorev_tamamlama(test_db):
    task = create_task("Bitecek görev")

    guncel = complete_task(task.id)

    assert guncel.done is True
    assert guncel.completed_at is not None


def test_liste_oncelige_gore_siralanir(test_db):
    create_task("Düşük", priority=1)
    create_task("Yüksek", priority=3)
    create_task("Orta", priority=2)

    gorevler = list_tasks()

    oncelikler = [g.priority for g in gorevler]
    assert oncelikler == [3, 2, 1]


def test_gecersiz_sure_hata_verir(test_db):
    with pytest.raises(ValueError):
        create_task("Görev", duration_minutes=0)


def test_gorev_gune_gore_filtrelenir(test_db):
    bugun = date.today()
    yarin = bugun + timedelta(days=1)
    create_task("Bugünkü", due_date=bugun)
    create_task("Yarınki", due_date=yarin)

    gorevler = list_tasks(due_date=bugun)

    assert [g.title for g in gorevler] == ["Bugünkü"]


def test_ertelenmemis_gorev_erteleme_sayaci_artmaz(test_db):
    yarin = date.today() + timedelta(days=1)
    task = create_task("Görev", due_date=yarin)

    guncel = update_task(task.id, task.title, task.description, task.priority, due_date=yarin + timedelta(days=1))

    assert guncel.postponement_count == 0


def test_gecikmis_gorev_ileri_tarihe_ertelenince_sayac_artar(test_db):
    gecmis = date.today() - timedelta(days=5)
    task = create_task("Gecikmiş görev", due_date=gecmis)

    # Hâlâ gecikmiş bir tarihe itiliyor (today-5 -> today-2): yine de bir erteleme.
    guncel = update_task(task.id, task.title, task.description, task.priority,
                          due_date=gecmis + timedelta(days=3))
    assert guncel.postponement_count == 1

    # Şimdi geleceğe itiliyor: eski tarih hâlâ gecikmiş olduğu için yine sayılır.
    tekrar = update_task(guncel.id, guncel.title, guncel.description, guncel.priority,
                          due_date=date.today() + timedelta(days=1))
    assert tekrar.postponement_count == 2


def test_gecikmis_gorev_erken_tarihe_cekilirse_sayac_artmaz(test_db):
    gecmis = date.today() - timedelta(days=3)
    task = create_task("Görev", due_date=gecmis)

    guncel = update_task(task.id, task.title, task.description, task.priority,
                          due_date=gecmis - timedelta(days=1))

    assert guncel.postponement_count == 0


def test_due_date_yoksa_sayac_artmaz(test_db):
    task = create_task("Görev")

    guncel = update_task(task.id, task.title, task.description, task.priority, due_date=date.today())

    assert guncel.postponement_count == 0


def test_tamamlanmis_gecikmis_gorev_ertelenince_sayac_artmaz(test_db):
    gecmis = date.today() - timedelta(days=3)
    task = create_task("Görev", due_date=gecmis)
    complete_task(task.id)

    guncel = update_task(task.id, task.title, task.description, task.priority,
                          due_date=date.today() + timedelta(days=1))

    assert guncel.postponement_count == 0


def test_gecikmis_gorevler_listelenir(test_db):
    bugun = date.today()
    gecmis = bugun - timedelta(days=2)
    create_task("Gecikmiş", due_date=gecmis)

    gecikmisler = gecikmis_gorevleri_listele(bugun)

    assert [g.title for g in gecikmisler] == ["Gecikmiş"]


def test_tamamlanmis_gecikmis_gorev_listelenmez(test_db):
    bugun = date.today()
    gecmis = bugun - timedelta(days=2)
    task = create_task("Tamamlanmış", due_date=gecmis)
    complete_task(task.id)

    assert gecikmis_gorevleri_listele(bugun) == []


def test_bugunku_ve_gelecek_gorevler_gecikmis_sayilmaz(test_db):
    bugun = date.today()
    create_task("Bugünkü", due_date=bugun)
    create_task("Gelecek", due_date=bugun + timedelta(days=1))
    create_task("Tarihsiz")

    assert gecikmis_gorevleri_listele(bugun) == []