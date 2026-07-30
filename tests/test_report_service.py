"""report_service için birim testleri."""

from datetime import date, datetime, time, timedelta

from core.models import PlanKaydi, Profil, Task
from core.services import report_service
from core.services.report_service import (
    haftalik_rapor,
    haftalik_trend,
    rutin_performans_ozeti,
    verimli_saat_onerisi,
)
from core.services.rutin_service import create_rutin, haftalik_rutinleri_uret
from core.services.task_service import complete_task, create_task, update_task

VARSAYILAN_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
)


def _plan_kaydi_ekle(user_id, gun, dilimler):
    with report_service.SessionLocal() as session:
        kayit = PlanKaydi(user_id=user_id, gun=gun, dilimler=dilimler, toplam_is_dakika=0, bos_zaman_dakika=0)
        session.add(kayit)
        session.commit()
        session.refresh(kayit)
        return kayit


def test_sifir_gorevde_bolme_hatasi_olmaz(test_db, test_user_id):
    rapor = haftalik_rapor(test_user_id, bitis=date(2026, 7, 6))

    assert rapor["verimlilik_orani"] == 0
    assert rapor["erteleme_orani"] == 0
    assert rapor["en_cok_ertelenenler"] == []
    assert all(v == 0 for v in rapor["saat_dilimi_verimi"].values())


def test_verimlilik_ve_erteleme_oranlari(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gecmis = gun - timedelta(days=10)

    tamamlanan = create_task(test_user_id, "Tamamlanan iş", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)

    create_task(test_user_id, "Bitmemiş iş", due_date=gun)

    ertelenen = create_task(test_user_id, "Ertelenen iş", due_date=gecmis)
    update_task(test_user_id, ertelenen.id, ertelenen.title, ertelenen.description, ertelenen.priority, due_date=gun)

    rapor = haftalik_rapor(test_user_id, bitis=gun, gun_sayisi=30)

    assert rapor["tamamlanan_sayisi"] == 1
    assert rapor["ertelenen_sayisi"] == 1
    assert rapor["verimlilik_orani"] == round(1 / 3 * 100)
    assert rapor["erteleme_orani"] == round(1 / 3 * 100)
    assert rapor["en_cok_ertelenenler"] == ["Ertelenen iş — 1 kez ertelendi"]


def test_saat_dilimi_verimi_tamamlanan_gorevi_yansitir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    tamamlanan = create_task(test_user_id, "Sabah işi", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)
    bitmemis = create_task(test_user_id, "Öğlen işi", due_date=gun)

    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": tamamlanan.id, "title": tamamlanan.title, "start": "07:30", "end": "08:00",
         "duration_minutes": 30, "gerekce": "..."},
        {"task_id": bitmemis.id, "title": bitmemis.title, "start": "11:00", "end": "11:30",
         "duration_minutes": 30, "gerekce": "..."},
    ])

    rapor = haftalik_rapor(test_user_id, bitis=gun)

    assert rapor["saat_dilimi_verimi"]["07–10"] == 100
    assert rapor["saat_dilimi_verimi"]["10–13"] == 0


def test_yeniden_uretilen_plan_sadece_sonuncusu_sayilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    eski_gorev = create_task(test_user_id, "Eski dilim görevi", due_date=gun)
    complete_task(test_user_id, eski_gorev.id)
    yeni_gorev = create_task(test_user_id, "Yeni dilim görevi", due_date=gun)

    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": eski_gorev.id, "title": eski_gorev.title, "start": "07:30", "end": "08:00",
         "duration_minutes": 30, "gerekce": "..."},
    ])
    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": yeni_gorev.id, "title": yeni_gorev.title, "start": "11:00", "end": "11:30",
         "duration_minutes": 30, "gerekce": "..."},
    ])

    rapor = haftalik_rapor(test_user_id, bitis=gun)

    # Sadece en son PlanKaydi sayılmalı: 10-13 dilimi 1 kayıt (tamamlanmamış), 07-10 hiç yok.
    assert rapor["saat_dilimi_verimi"]["07–10"] == 0
    assert rapor["saat_dilimi_verimi"]["10–13"] == 0


def test_cok_ertelenen_gorev_icin_oneri_uretilir(test_db, test_user_id):
    gun = date(2026, 7, 6)
    gecmis = gun - timedelta(days=20)
    gorev = create_task(test_user_id, "Sık ertelenen iş", due_date=gecmis)
    for i in range(3):
        gorev = update_task(
            test_user_id, gorev.id, gorev.title, gorev.description, gorev.priority,
            due_date=gecmis + timedelta(days=i + 1),
        )

    rapor = haftalik_rapor(test_user_id, bitis=gun, gun_sayisi=30, profil=VARSAYILAN_PROFIL)

    assert any("Sık ertelenen iş" in oneri for oneri in rapor["erteleme_onerileri"])


def test_profilsiz_cagrida_erteleme_onerileri_bos_liste_doner(test_db, test_user_id):
    rapor = haftalik_rapor(test_user_id, bitis=date(2026, 7, 6))

    assert rapor["erteleme_onerileri"] == []


def test_etkinlik_verimlilik_oranini_etkilemez(test_db, test_user_id):
    gun = date(2026, 7, 6)
    tamamlanan = create_task(test_user_id, "Tamamlanan iş", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)

    with report_service.SessionLocal() as session:
        session.add(Task(
            user_id=test_user_id, tur="etkinlik", title="Toplantı", due_date=gun,
            start="2026-07-06T09:00:00", end="2026-07-06T10:00:00", updated="",
        ))
        session.commit()

    rapor = haftalik_rapor(test_user_id, bitis=gun)

    # Etkinlik satırı "tamamlanmamış görev" gibi sayılmamalı: tek görev var, o da tamamlandı.
    assert rapor["verimlilik_orani"] == 100
    assert rapor["tamamlanan_sayisi"] == 1


def test_rutin_performans_ozeti_dogru_oran_hesaplar(test_db, test_user_id):
    from datetime import time as dt_time

    rutin = create_rutin(test_user_id, "Spor", [0, 2], dt_time(18, 0))
    haftalik_rutinleri_uret(test_user_id, date(2026, 7, 6))  # Pazartesi(0) ve Çarşamba(2) üretir

    with report_service.SessionLocal() as session:
        gorevler = session.query(Task).filter(Task.rutin_id == rutin.id).all()
        gorevler[0].completed_at = datetime(2026, 7, 6, 19, 0)
        session.commit()

    ozet = rutin_performans_ozeti(test_user_id, bitis=date(2026, 7, 12))

    assert ozet == [{"baslik": "Spor", "toplam": 2, "tamamlanan": 1, "oran": 50}]


def test_haftalik_trend_dogru_sirada_ve_uzunlukta_doner(test_db, test_user_id):
    gun = date(2026, 7, 6)
    tamamlanan = create_task(test_user_id, "İş", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)

    trend = haftalik_trend(test_user_id, bitis=gun, hafta_sayisi=4)

    assert len(trend) == 4
    assert [n["hafta_bitis"] for n in trend] == sorted(n["hafta_bitis"] for n in trend)
    assert trend[-1]["hafta_bitis"] == gun
    assert trend[-1]["verimlilik_orani"] == 100


def test_verimli_saat_onerisi_veri_yoksa_none_doner(test_db, test_user_id):
    assert verimli_saat_onerisi(test_user_id) is None


def test_verimli_saat_onerisi_esik_altindaysa_none_doner(test_db, test_user_id):
    gun = date.today()
    tamamlanan = create_task(test_user_id, "Sabah işi 1", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)
    bitmemis = create_task(test_user_id, "Sabah işi 2", due_date=gun)

    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": tamamlanan.id, "title": tamamlanan.title, "start": "07:30", "end": "08:00",
         "duration_minutes": 30, "gerekce": "..."},
        {"task_id": bitmemis.id, "title": bitmemis.title, "start": "08:30", "end": "09:00",
         "duration_minutes": 30, "gerekce": "..."},
    ])

    assert verimli_saat_onerisi(test_user_id) is None


def test_verimli_saat_onerisi_profil_zaten_ayniysa_none_doner(test_db, test_user_id):
    gun = date.today()
    tamamlanan = create_task(test_user_id, "Sabah işi", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)

    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": tamamlanan.id, "title": tamamlanan.title, "start": "07:30", "end": "08:00",
         "duration_minutes": 30, "gerekce": "..."},
    ])

    profil = Profil(
        ad_soyad="Test", verimli_baslangic=time(7, 0), verimli_bitis=time(10, 0),
        uyku_baslangic=time(23, 0), uyku_bitis=time(7, 0), gunluk_hedef=5,
    )

    assert verimli_saat_onerisi(test_user_id, profil=profil) is None


def test_verimli_saat_onerisi_gercek_oneri_uretir(test_db, test_user_id):
    gun = date.today()
    tamamlanan = create_task(test_user_id, "Sabah işi", due_date=gun)
    complete_task(test_user_id, tamamlanan.id)

    _plan_kaydi_ekle(test_user_id, gun, [
        {"task_id": tamamlanan.id, "title": tamamlanan.title, "start": "07:30", "end": "08:00",
         "duration_minutes": 30, "gerekce": "..."},
    ])

    oneri = verimli_saat_onerisi(test_user_id, profil=VARSAYILAN_PROFIL)

    assert oneri == {"baslangic": time(7, 0), "bitis": time(10, 0), "yuzde": 100}


def test_baska_kullanicinin_verisi_karismaz(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_rapor", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    gun = date(2026, 7, 6)
    diger_gorev = create_task(diger_id, "Diğer kullanıcının işi", due_date=gun)
    complete_task(diger_id, diger_gorev.id)

    rapor = haftalik_rapor(test_user_id, bitis=gun)

    assert rapor["tamamlanan_sayisi"] == 0
