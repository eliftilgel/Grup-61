"""degerlendirme_service için birim testleri."""

from datetime import date, time

from core.models import Profil
from core.services.degerlendirme_service import gun_sonu_degerlendirmesi_uret
from core.services.planning_service import plan_olustur
from core.services.task_service import complete_task, create_task

VARSAYILAN_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
)


def test_plan_yoksa_none_doner(test_db, test_user_id):
    assert gun_sonu_degerlendirmesi_uret(test_user_id, date(2026, 7, 6)) is None


def test_plan_dilimleri_bossa_none_doner(test_db, test_user_id):
    gun = date(2026, 7, 6)
    plan_olustur(test_user_id, gun, [], [], VARSAYILAN_PROFIL)

    assert gun_sonu_degerlendirmesi_uret(test_user_id, gun) is None


def test_tum_gorevler_tamamlaninca_yuz_oran_ve_ovgu_yorumu(test_db, test_user_id):
    gun = date(2026, 7, 6)
    birinci = create_task(test_user_id, "Rapor yaz", priority=2, duration_minutes=30, due_date=gun)
    ikinci = create_task(test_user_id, "Email cevapla", priority=1, duration_minutes=20, due_date=gun)
    plan_olustur(test_user_id, gun, [birinci, ikinci], [], VARSAYILAN_PROFIL)
    complete_task(test_user_id, birinci.id)
    complete_task(test_user_id, ikinci.id)

    sonuc = gun_sonu_degerlendirmesi_uret(test_user_id, gun)

    assert sonuc["planlanan_sayisi"] == 2
    assert sonuc["tamamlanan_sayisi"] == 2
    assert sonuc["tamamlama_orani"] == 100
    assert sonuc["tamamlanmayanlar"] == []
    assert "Harika" in sonuc["yorum"]


def test_kismi_tamamlaninca_dogru_oran_ve_tamamlanmayanlar_listesi(test_db, test_user_id):
    gun = date(2026, 7, 6)
    tamamlanan = create_task(test_user_id, "Rapor yaz", priority=2, duration_minutes=30, due_date=gun)
    tamamlanmayan = create_task(test_user_id, "Email cevapla", priority=1, duration_minutes=20, due_date=gun)
    plan_olustur(test_user_id, gun, [tamamlanan, tamamlanmayan], [], VARSAYILAN_PROFIL)
    complete_task(test_user_id, tamamlanan.id)

    sonuc = gun_sonu_degerlendirmesi_uret(test_user_id, gun)

    assert sonuc["planlanan_sayisi"] == 2
    assert sonuc["tamamlanan_sayisi"] == 1
    assert sonuc["tamamlama_orani"] == 50
    assert sonuc["tamamlanmayanlar"] == ["Email cevapla"]


def test_hic_tamamlanmayinca_dusuk_oran_yorumu(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "Rapor yaz", priority=2, duration_minutes=30, due_date=gun)
    plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL)

    sonuc = gun_sonu_degerlendirmesi_uret(test_user_id, gun)

    assert sonuc["tamamlama_orani"] == 0
    assert "daha gerçekçi" in sonuc["yorum"]
