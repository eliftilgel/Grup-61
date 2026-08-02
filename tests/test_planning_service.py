"""planning_service için birim testleri."""

from datetime import date, datetime, time

from core.models import Profil, Task
from core.services.planning_service import (
    alternatif_planlari_uret,
    bosluk_analizi_yap,
    erteleme_onerilerini_uret,
    erteleme_onerisi_uret,
    kapasite_kontrolu,
    kullanicinin_planlari,
    plan_olustur,
    son_plan,
)
from core.services.task_service import create_task

VARSAYILAN_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
)

BUFFERLI_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
    buffer_dakika=15,
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


def _enerji_test_gorevleri_ekle(test_user_id, gun):
    kisa_dusuk = create_task(test_user_id, "Kısa düşük öncelik", priority=1, duration_minutes=15, due_date=gun)
    uzun_yuksek = create_task(test_user_id, "Uzun yüksek öncelik", priority=3, duration_minutes=30, due_date=gun)
    return kisa_dusuk, uzun_yuksek


_ENERJI_TEK_SLOT_DISINDA_KAPAT = [
    {"start": time(6, 0), "end": time(9, 0), "label": "Meşgul"},
    {"start": time(9, 30), "end": time(23, 0), "label": "Meşgul"},
]


def test_dusuk_enerjide_kisa_dusuk_oncelikli_gorev_once_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    kayit = plan_olustur(
        test_user_id, gun, [uzun_yuksek, kisa_dusuk], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
        enerji_seviyesi="dusuk",
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert kisa_dusuk.id in yerlesen_ids
    assert uzun_yuksek.id not in yerlesen_ids


def test_yuksek_enerjide_uzun_yuksek_oncelikli_gorev_once_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    kayit = plan_olustur(
        test_user_id, gun, [uzun_yuksek, kisa_dusuk], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
        enerji_seviyesi="yuksek",
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert uzun_yuksek.id in yerlesen_ids
    assert kisa_dusuk.id not in yerlesen_ids


def test_enerji_belirtilmezse_mevcut_oncelik_sirasi_korunur(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    kayit = plan_olustur(
        test_user_id, gun, [uzun_yuksek, kisa_dusuk], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert uzun_yuksek.id in yerlesen_ids
    assert kisa_dusuk.id not in yerlesen_ids


def test_orta_enerjide_mevcut_oncelik_sirasi_korunur(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    kayit = plan_olustur(
        test_user_id, gun, [uzun_yuksek, kisa_dusuk], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
        enerji_seviyesi="orta",
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert uzun_yuksek.id in yerlesen_ids
    assert kisa_dusuk.id not in yerlesen_ids


def test_enerji_seviyesi_plan_kaydina_yazilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL, enerji_seviyesi="yuksek")

    assert kayit.enerji_seviyesi == "yuksek"


def test_dusuk_enerji_genel_tavsiyeye_not_ekler(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL, enerji_seviyesi="dusuk")

    assert "düşük enerji" in kayit.genel_tavsiye.lower()


def test_kesin_gorev_dusuk_oncelikli_olsa_da_once_yerlestirilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    # Gün boyunca tek boşluk 07:00-08:00 (60 dk) kalacak şekilde her yeri kapat.
    tek_slot_disinda_kapat = [{"start": time(8, 0), "end": time(23, 0), "label": "Meşgul"}]
    kesin_dusuk = create_task(
        test_user_id, "Kesin ama düşük öncelikli", priority=1, duration_minutes=60, due_date=gun,
        teslim_tipi="kesin", kesin_bitis=datetime(2026, 7, 6, 9, 0),
    )
    esnek_kritik = create_task(
        test_user_id, "Esnek ama kritik", priority=3, duration_minutes=60, due_date=gun,
    )

    kayit = plan_olustur(
        test_user_id, gun, [esnek_kritik, kesin_dusuk], tek_slot_disinda_kapat, VARSAYILAN_PROFIL
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert kesin_dusuk.id in yerlesen_ids
    assert esnek_kritik.id not in yerlesen_ids
    kesin_dilim = next(d for d in kayit.dilimler if d["task_id"] == kesin_dusuk.id)
    assert "kesin" in kesin_dilim["gerekce"].lower()


def _sabit_saatli_gorev_ekle(test_db, user_id, gun, saat, duration_minutes=30, priority=2, teslim_tipi="esnek"):
    with test_db() as session:
        task = Task(
            user_id=user_id, title="Rutin görevi", tur="gorev", due_date=gun,
            duration_minutes=duration_minutes, priority=priority, teslim_tipi=teslim_tipi,
            sabit_saat=saat,
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        return task


def test_sabit_saatli_gorev_tam_saatine_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    rutin_gorevi = _sabit_saatli_gorev_ekle(test_db, test_user_id, gun, time(18, 0))

    kayit = plan_olustur(test_user_id, gun, [rutin_gorevi], [], VARSAYILAN_PROFIL)

    assert kayit.dilimler[0]["start"] == "18:00"
    assert "rutin" in kayit.dilimler[0]["gerekce"].lower()


def test_sabit_saat_doluysa_tercih_penceresine_duser(test_db, test_user_id):
    gun = date(2026, 7, 6)
    rutin_gorevi = _sabit_saatli_gorev_ekle(test_db, test_user_id, gun, time(18, 0), priority=2)
    saati_kapatan_blok = [{"start": time(18, 0), "end": time(18, 30), "label": "Meşgul"}]

    kayit = plan_olustur(test_user_id, gun, [rutin_gorevi], saati_kapatan_blok, VARSAYILAN_PROFIL)

    assert kayit.dilimler[0]["start"] != "18:00"
    assert "13:00" <= kayit.dilimler[0]["start"] < "18:00"
    assert "başka bir şey vardı" in kayit.dilimler[0]["gerekce"]


def test_sabit_saatli_gorev_kesin_gorevden_once_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    # Tek boşluk 18:00-18:30 kalacak şekilde her yeri kapat.
    tek_slot_disinda_kapat = [
        {"start": time(6, 0), "end": time(18, 0), "label": "Meşgul"},
        {"start": time(18, 30), "end": time(23, 0), "label": "Meşgul"},
    ]
    sabit_gorev = _sabit_saatli_gorev_ekle(test_db, test_user_id, gun, time(18, 0), duration_minutes=30, priority=1)
    kesin_gorev = create_task(
        test_user_id, "Kesin görev", priority=3, duration_minutes=30, due_date=gun,
        teslim_tipi="kesin", kesin_bitis=datetime(2026, 7, 6, 19, 0),
    )

    kayit = plan_olustur(
        test_user_id, gun, [kesin_gorev, sabit_gorev], tek_slot_disinda_kapat, VARSAYILAN_PROFIL
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert sabit_gorev.id in yerlesen_ids
    assert kesin_gorev.id not in yerlesen_ids


def test_buffer_yoksa_gorevler_yapisik_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    birinci = create_task(test_user_id, "Birinci", priority=3, duration_minutes=60, due_date=gun)
    ikinci = create_task(test_user_id, "İkinci", priority=3, duration_minutes=60, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [birinci, ikinci], [], VARSAYILAN_PROFIL)

    dilimler = sorted(kayit.dilimler, key=lambda d: d["start"])
    assert dilimler[0]["end"] == dilimler[1]["start"]


def test_buffer_varsa_gorevler_arasinda_bosluk_birakilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    birinci = create_task(test_user_id, "Birinci", priority=3, duration_minutes=60, due_date=gun)
    ikinci = create_task(test_user_id, "İkinci", priority=3, duration_minutes=60, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [birinci, ikinci], [], BUFFERLI_PROFIL)

    dilimler = sorted(kayit.dilimler, key=lambda d: d["start"])
    birinci_bitis_dk = int(dilimler[0]["end"][:2]) * 60 + int(dilimler[0]["end"][3:])
    ikinci_baslangic_dk = int(dilimler[1]["start"][:2]) * 60 + int(dilimler[1]["start"][3:])
    assert ikinci_baslangic_dk >= birinci_bitis_dk + 15


def test_esik_altindaki_gorev_oneri_almaz():
    az_ertelenen = Task(title="Az ertelenen", duration_minutes=30, postponement_count=2)

    assert erteleme_onerilerini_uret([az_ertelenen], VARSAYILAN_PROFIL) == []


def test_esik_ustundeki_gorev_saat_onerisi_alir():
    cok_ertelenen = Task(title="Rapor yaz", duration_minutes=30, postponement_count=3)

    oneri = erteleme_onerisi_uret(cok_ertelenen, VARSAYILAN_PROFIL)

    assert "Rapor yaz" in oneri
    assert "07:00" in oneri


def test_buyuk_gorev_bolme_onerisi_alir():
    buyuk_gorev = Task(title="Büyük proje", duration_minutes=120, postponement_count=3)

    oneri = erteleme_onerisi_uret(buyuk_gorev, VARSAYILAN_PROFIL)

    assert "böl" in oneri.lower()


def test_profilsiz_de_genel_oneri_uretilir():
    cok_ertelenen = Task(title="Görev", duration_minutes=30, postponement_count=5)

    oneri = erteleme_onerisi_uret(cok_ertelenen, profil=None)

    assert "Görev" in oneri


def test_kapasite_uygun_olmayan_bloklari_dikkate_alir(test_db, test_user_id):
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30)
    tam_gun_blogu = [{"start": time(7, 0), "end": time(23, 0), "label": "Meşgul"}]

    sonuc = kapasite_kontrolu([gorev], tam_gun_blogu, VARSAYILAN_PROFIL)

    assert sonuc["musait_dakika"] == 0
    assert sonuc["asiri_yuklenme"] is True
    assert sonuc["fark_dakika"] == 30


_STRATEJI_TEK_SLOT_DISINDA_KAPAT = [{"start": time(7, 30), "end": time(23, 0), "label": "Meşgul"}]


def test_sabah_yogun_stratejisinde_uzun_gorev_once_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    kisa = create_task(test_user_id, "Kısa", priority=2, duration_minutes=10, due_date=gun)
    uzun = create_task(test_user_id, "Uzun", priority=2, duration_minutes=25, due_date=gun)

    kayit = plan_olustur(
        test_user_id, gun, [kisa, uzun], _STRATEJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
        strateji="sabah_yogun",
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert uzun.id in yerlesen_ids
    assert kisa.id not in yerlesen_ids


def test_dengeli_dagitim_stratejisinde_id_sirasi_korunur(test_db, test_user_id):
    gun = date(2026, 7, 6)
    once_olusturulan = create_task(test_user_id, "Önce", priority=1, duration_minutes=20, due_date=gun)
    sonra_olusturulan = create_task(test_user_id, "Sonra", priority=3, duration_minutes=20, due_date=gun)

    kayit = plan_olustur(
        test_user_id, gun, [sonra_olusturulan, once_olusturulan], _STRATEJI_TEK_SLOT_DISINDA_KAPAT,
        VARSAYILAN_PROFIL, strateji="dengeli_dagitim",
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert once_olusturulan.id in yerlesen_ids
    assert sonra_olusturulan.id not in yerlesen_ids


def test_plan_olustur_strateji_plan_kaydina_yazilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL, strateji="sabah_yogun")

    assert kayit.strateji == "sabah_yogun"


def test_strateji_belirtilmezse_varsayilan_kaydedilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL)

    assert kayit.strateji == "oncelik_agirlikli"


def test_alternatif_planlari_uret_uc_strateji_dondurur_ve_kaydetmez(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "İş", priority=2, duration_minutes=30, due_date=gun)
    onceki_sayisi = len(kullanicinin_planlari(test_user_id))

    sonuc = alternatif_planlari_uret([gorev], [], VARSAYILAN_PROFIL)

    assert set(sonuc.keys()) == {"oncelik_agirlikli", "sabah_yogun", "dengeli_dagitim"}
    for hesap in sonuc.values():
        assert "dilimler" in hesap and "toplam_is_dakika" in hesap
    assert len(kullanicinin_planlari(test_user_id)) == onceki_sayisi


def test_havuz_gorevi_kalan_bosluga_yerlesir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    aktif = create_task(test_user_id, "Aktif görev", priority=2, duration_minutes=20, due_date=gun)
    havuz_kucuk = create_task(test_user_id, "Küçük havuz görevi", priority=1, duration_minutes=10)
    havuz_buyuk = create_task(test_user_id, "Büyük havuz görevi", priority=1, duration_minutes=15)

    kayit = plan_olustur(
        test_user_id, gun, [aktif, havuz_kucuk, havuz_buyuk], _STRATEJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert aktif.id in yerlesen_ids
    assert havuz_kucuk.id in yerlesen_ids
    assert havuz_buyuk.id not in yerlesen_ids


def test_plan_olustur_yerlesen_havuz_gorevinin_due_date_ini_gunceller(test_db, test_user_id):
    gun = date(2026, 7, 6)
    aktif = create_task(test_user_id, "Aktif görev", priority=2, duration_minutes=20, due_date=gun)
    havuz_kucuk = create_task(test_user_id, "Küçük havuz görevi", priority=1, duration_minutes=10)
    havuz_buyuk = create_task(test_user_id, "Büyük havuz görevi", priority=1, duration_minutes=15)

    plan_olustur(
        test_user_id, gun, [aktif, havuz_kucuk, havuz_buyuk], _STRATEJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    with test_db() as session:
        assert session.get(Task, havuz_kucuk.id).due_date == gun
        assert session.get(Task, havuz_buyuk.id).due_date is None


def test_alternatif_planlari_uret_havuz_gorevini_onizler_ama_due_date_degistirmez(test_db, test_user_id):
    gun = date(2026, 7, 6)
    aktif = create_task(test_user_id, "Aktif görev", priority=2, duration_minutes=20, due_date=gun)
    havuz = create_task(test_user_id, "Havuz görevi", priority=1, duration_minutes=10)

    sonuc = alternatif_planlari_uret(
        [aktif, havuz], _STRATEJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    havuz_yerlesti = any(
        d["task_id"] == havuz.id and d["havuzdan"] for d in sonuc["oncelik_agirlikli"]["dilimler"]
    )
    assert havuz_yerlesti

    with test_db() as session:
        assert session.get(Task, havuz.id).due_date is None


def test_dilimde_havuzdan_alani_dogru_gelir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    aktif = create_task(test_user_id, "Aktif görev", priority=2, duration_minutes=20, due_date=gun)
    havuz = create_task(test_user_id, "Havuz görevi", priority=1, duration_minutes=10)

    kayit = plan_olustur(
        test_user_id, gun, [aktif, havuz], _STRATEJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    dilim_by_id = {d["task_id"]: d for d in kayit.dilimler}
    assert dilim_by_id[aktif.id]["havuzdan"] is False
    assert dilim_by_id[havuz.id]["havuzdan"] is True


# --- ai_sira: Gemini'nin sıralama önerisi (opt-in, varsayılan davranışı değiştirmez) -------------


def test_ai_sira_verilmezse_davranis_degismez(test_db, test_user_id):
    """ai_sira parametresi hiç geçirilmezse (varsayılan None), mevcut önceliğe dayalı
    sıralama birebir korunur — bu, mevcut testlerin (ai_sira'sız) hiç kırılmayacağının
    açık bir güvencesi."""
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    kayit = plan_olustur(
        test_user_id, gun, [kisa_dusuk, uzun_yuksek], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert uzun_yuksek.id in yerlesen_ids  # varsayılan öncelik sırası: yüksek öncelik kazanır
    assert kisa_dusuk.id not in yerlesen_ids


def test_ai_sira_gecerliyse_siralamayi_degistirir(test_db, test_user_id):
    """Geçerli bir ai_sira verildiğinde, düşük öncelikli görev bile Gemini'nin
    önerdiği sırayla tek boş slotu kazanabilir — gerçek karar yetkisinin kanıtı."""
    gun = date(2026, 7, 6)
    kisa_dusuk, uzun_yuksek = _enerji_test_gorevleri_ekle(test_user_id, gun)

    ai_sira = {kisa_dusuk.id: 0, uzun_yuksek.id: 1}  # Gemini düşük öncelikliyi önce istiyor
    kayit = plan_olustur(
        test_user_id, gun, [kisa_dusuk, uzun_yuksek], _ENERJI_TEK_SLOT_DISINDA_KAPAT, VARSAYILAN_PROFIL,
        ai_sira=ai_sira,
    )

    yerlesen_ids = {d["task_id"] for d in kayit.dilimler}
    assert kisa_dusuk.id in yerlesen_ids  # ai_sira'nın önerdiği sırayla düşük öncelikli kazandı
    assert uzun_yuksek.id not in yerlesen_ids


def test_ai_sira_sabit_saatli_gorevi_asla_etkilemez(test_db, test_user_id):
    """ai_sira sadece grup 2'yi (bugüne ait esnek görevler) etkiler — sabit saatli
    (rutin) bir görev, ai_sira'da her ne yazarsa yazsın her zaman kendi saatine yerleşir."""
    gun = date(2026, 7, 6)
    rutin = _sabit_saatli_gorev_ekle(test_db, test_user_id, gun, time(18, 0), priority=1)
    esnek = create_task(test_user_id, "Esnek", priority=3, duration_minutes=30, due_date=gun)

    # ai_sira, esnek görevi rutinden "önce" istiyor gibi görünse de — grup 0 hep ilk yerleşir.
    kayit = plan_olustur(
        test_user_id, gun, [rutin, esnek], [], VARSAYILAN_PROFIL, ai_sira={esnek.id: 0, rutin.id: 1},
    )

    rutin_dilim = next(d for d in kayit.dilimler if d["task_id"] == rutin.id)
    assert rutin_dilim["start"] == "18:00"


def test_tavsiye_uret_enjekte_edilirse_kullanilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "Görev", priority=2, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(
        test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL,
        tavsiye_uret=lambda *a, **k: "sahte tavsiye metni",
    )

    assert kayit.genel_tavsiye == "sahte tavsiye metni"


def test_oneri_uret_enjekte_edilirse_kullanilir(test_db, test_user_id):
    gorev = create_task(
        test_user_id, "Ertelenen görev", priority=2, duration_minutes=30,
        due_date=date(2026, 7, 6),
    )
    gorev.postponement_count = 5  # eşik (3) üzerinde

    sonuc = erteleme_onerilerini_uret([gorev], VARSAYILAN_PROFIL, oneri_uret=lambda t, p: "sahte öneri")

    assert sonuc == ["sahte öneri"]


# --- bosluk_analizi_yap (yoğunlaşma tespiti) ------------------------------------------------


def test_bosluk_analizi_buyuk_bosluk_tespit_eder(test_db, test_user_id):
    """ayse_yilmaz senaryosuyla aynı desen: tek bir kritik (sabah) ve birkaç düşük
    (akşam) öncelikli görev var, ORTA öncelikli hiçbir görev yok — 13:00-18:00
    penceresi tamamen boş kalır ve büyük bir boşluk olarak tespit edilmeli."""
    gun = date(2026, 7, 6)
    kritik = create_task(test_user_id, "Kritik iş", priority=3, duration_minutes=60, due_date=gun)
    dusuk = create_task(test_user_id, "Düşük iş", priority=1, duration_minutes=60, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [kritik, dusuk], [], VARSAYILAN_PROFIL)

    bosluk = bosluk_analizi_yap(kayit, VARSAYILAN_PROFIL)

    assert bosluk is not None
    assert bosluk["sure_dakika"] >= 180


def test_bosluk_analizi_gun_yogun_doluysa_none_doner(test_db, test_user_id):
    """Gün, aralarında büyük boşluk bırakmayacak şekilde (rutin/sabit saatli
    görevlerle) sık aralıklarla dolduysa None dönmeli."""
    gun = date(2026, 7, 6)
    for saat in (7, 9, 11, 13, 15, 17, 19, 21):
        _sabit_saatli_gorev_ekle(test_db, test_user_id, gun, time(saat, 0), duration_minutes=30)

    kayit = plan_olustur(test_user_id, gun, [], [], VARSAYILAN_PROFIL)

    assert bosluk_analizi_yap(kayit, VARSAYILAN_PROFIL) is None


def test_bosluk_analizi_tek_gorevde_none_doner(test_db, test_user_id):
    gun = date(2026, 7, 6)
    tek_gorev = create_task(test_user_id, "Tek görev", priority=3, duration_minutes=30, due_date=gun)

    kayit = plan_olustur(test_user_id, gun, [tek_gorev], [], VARSAYILAN_PROFIL)

    assert bosluk_analizi_yap(kayit, VARSAYILAN_PROFIL) is None


def test_bosluk_analizi_uygun_olmayan_blogu_yanlislikla_yogunlasma_saymaz(test_db, test_user_id):
    """08:00-20:00 arası gerçek bir kısıtla (ör. ders) meşgulse, bu bir 'yoğunlaşma'
    değildir — bloklar doğru geçirildiğinde false positive olmamalı. Bloklar
    geçirilmediğinde (eski/varsayılan davranış) aynı boşluk yanlışlıkla
    yoğunlaşma sayılabilir; iki çağrı karşılaştırılarak bu risk somutlaştırılıyor."""
    gun = date(2026, 7, 6)
    kritik = create_task(test_user_id, "Sabah işi", priority=3, duration_minutes=60, due_date=gun)
    dusuk = create_task(test_user_id, "Akşam işi", priority=1, duration_minutes=60, due_date=gun)
    ders_blogu = [{"start": time(8, 0), "end": time(20, 0), "label": "Ders"}]

    kayit = plan_olustur(test_user_id, gun, [kritik, dusuk], ders_blogu, VARSAYILAN_PROFIL)

    # Blok doğru geçirildiğinde: kalan gerçek boşluk eşik altında, false positive yok.
    assert bosluk_analizi_yap(kayit, VARSAYILAN_PROFIL, ders_blogu) is None
    # Blok geçirilmezse: 08:00-20:00 (ders zamanı) yanlışlıkla boşluk sayılır.
    assert bosluk_analizi_yap(kayit, VARSAYILAN_PROFIL) is not None
