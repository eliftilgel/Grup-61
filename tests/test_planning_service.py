"""planning_service için birim testleri."""

from datetime import date, time

from core.models import Profil
from core.services.planning_service import kapasite_kontrolu, kullanicinin_planlari, plan_olustur, son_plan
from core.services.task_service import create_task

VARSAYILAN_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
)


def test_temel_yerlestirme_ve_gerekce(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kritik = create_task(test_user_id, "Raporu yaz", priority=3, duration_minutes=120, due_date=gun)
    orta = create_task(test_user_id, "Email cevapla", priority=2, duration_minutes=30, due_date=gun)
    dusuk = create_task(test_user_id, "Masayı temizle", priority=1, duration_minutes=15, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [kritik, orta, dusuk], [], VARSAYILAN_PROFIL)

    assert len(kayit.dilimler) == 3
    assert all(d["gerekce"] for d in kayit.dilimler)
    assert kayit.toplam_is_dakika == 120 + 30 + 15
    kritik_dilim = next(d for d in kayit.dilimler if d["task_id"] == kritik.id)
    assert kritik_dilim["start"] == "07:00"


def test_uygun_olmayan_blok_verimli_pencereyi_kapatirsa_kritik_disari_tasar(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kritik = create_task(test_user_id, "Kritik iş", priority=3, duration_minutes=60, due_date=gun)
    tam_kapatan_blok = [{"start": time(7, 0), "end": time(13, 0), "label": "Ders"}]

    kayit = plan_olustur(test_user_id, gun, [kritik], tam_kapatan_blok, VARSAYILAN_PROFIL)

    assert len(kayit.dilimler) == 1
    assert kayit.dilimler[0]["start"] >= "13:00"


def test_uyku_penceresi_gece_yarisini_sarar(test_db, test_user_id):
    gun = date(2026, 7, 6)
    aksam_isi = create_task(test_user_id, "Akşam işi", priority=1, duration_minutes=60, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [aksam_isi], [], VARSAYILAN_PROFIL)

    dilim = kayit.dilimler[0]
    assert dilim["start"] < "23:00"
    assert dilim["end"] <= "23:00"


def test_gun_kapasitesi_asilirsa_gorev_yerlestirilmez(test_db, test_user_id):
    gun = date(2026, 7, 6)
    dev_gorev = create_task(test_user_id, "Çok uzun görev", priority=3, duration_minutes=2000, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [dev_gorev], [], VARSAYILAN_PROFIL)

    assert kayit.dilimler == []
    assert kayit.toplam_is_dakika == 0


def test_son_plan_en_son_kaydi_doner(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)

    ilk = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL)
    ikinci = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL)

    assert ilk.id != ikinci.id
    assert son_plan(test_user_id, gun).id == ikinci.id


def test_plan_olmayan_gun_none_doner(test_db, test_user_id):
    assert son_plan(test_user_id, date(2099, 1, 1)) is None


def test_kullanicinin_planlari_baska_kullaniciyi_gormez(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_planlayici", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=date(2026, 7, 6))
    plan_olustur(test_user_id, date(2026, 7, 6), [gorev], [], VARSAYILAN_PROFIL)

    assert kullanicinin_planlari(test_user_id) != []
    assert kullanicinin_planlari(diger_id) == []


def test_kapasite_asilmazsa_asiri_yuklenme_false(test_db, test_user_id):
    gorev = create_task(test_user_id, "Kısa iş", priority=2, duration_minutes=500)

    sonuc = kapasite_kontrolu([gorev], [], VARSAYILAN_PROFIL)

    assert sonuc["asiri_yuklenme"] is False
    assert sonuc["fark_dakika"] == 0
    assert sonuc["toplam_gorev_dakika"] == 500


def test_kapasite_asilirsa_asiri_yuklenme_true(test_db, test_user_id):
    # Gün 06:00-23:00 (1020 dk), uyku 23:00-07:00 sadece 06:00-07:00'ı (60 dk) kapsıyor.
    # Müsait: 1020 - 60 = 960 dk.
    gorev = create_task(test_user_id, "Uzun iş", priority=2, duration_minutes=1000)

    sonuc = kapasite_kontrolu([gorev], [], VARSAYILAN_PROFIL)

    assert sonuc["musait_dakika"] == 960
    assert sonuc["asiri_yuklenme"] is True
    assert sonuc["fark_dakika"] == 40


def test_kapasite_uygun_olmayan_bloklari_dikkate_alir(test_db, test_user_id):
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30)
    tam_gun_blogu = [{"start": time(7, 0), "end": time(23, 0), "label": "Meşgul"}]

    sonuc = kapasite_kontrolu([gorev], tam_gun_blogu, VARSAYILAN_PROFIL)

    assert sonuc["musait_dakika"] == 0
    assert sonuc["asiri_yuklenme"] is True
    assert sonuc["fark_dakika"] == 30
