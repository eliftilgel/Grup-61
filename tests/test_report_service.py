"""report_service için birim testleri."""

from datetime import date, timedelta

from core.models import PlanKaydi
from core.services import report_service
from core.services.report_service import haftalik_rapor
from core.services.task_service import complete_task, create_task, update_task


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
