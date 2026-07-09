"""task_service için birim testleri."""

import pytest

from core.services.task_service import complete_task, create_task, list_tasks


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


def test_liste_oncelige_gore_siralanir(test_db):
    create_task("Düşük", priority=1)
    create_task("Yüksek", priority=3)
    create_task("Orta", priority=2)

    gorevler = list_tasks()

    oncelikler = [g.priority for g in gorevler]
    assert oncelikler == [3, 2, 1]