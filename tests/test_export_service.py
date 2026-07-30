"""export_service için birim testleri."""

from datetime import date, datetime, time

from core.models import PlanKaydi, Task
from core.services import export_service
from core.services.profil_service import save as profil_kaydet
from core.services.task_service import create_task


def _etkinlik_ekle(user_id):
    with export_service.SessionLocal() as session:
        session.add(Task(
            user_id=user_id, tur="etkinlik", google_id="g1", title="Toplantı", description="",
            start="2026-07-10T09:00:00", end="2026-07-10T10:00:00", updated="2026-07-10T08:00:00",
        ))
        session.commit()


def _plan_kaydi_ekle(user_id):
    with export_service.SessionLocal() as session:
        session.add(PlanKaydi(
            user_id=user_id, gun=date(2026, 7, 10), dilimler=[], toplam_is_dakika=0, bos_zaman_dakika=0
        ))
        session.commit()


def test_bos_veritabaninda_bos_listeler_doner(test_db, test_user_id):
    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    assert yedek["gorevler"] == []
    assert yedek["takvim_etkinlikleri"] == []
    assert yedek["plan_kayitlari"] == []
    assert yedek["profil"] is None
    assert "disa_aktarma_tarihi" in yedek


def test_gorevler_dogru_serilestirilir(test_db, test_user_id):
    create_task(test_user_id, "Rapor yaz", priority=3, due_date=date(2026, 7, 10), duration_minutes=60)

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    assert len(yedek["gorevler"]) == 1
    gorev = yedek["gorevler"][0]
    assert gorev["title"] == "Rapor yaz"
    assert gorev["due_date"] == "2026-07-10"
    assert gorev["duration_minutes"] == 60


def test_gorev_konum_link_teslim_tipi_serilestirilir(test_db, test_user_id):
    create_task(test_user_id, "Sunum", konum="Ofis", link="https://example.com")

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    gorev = yedek["gorevler"][0]
    assert gorev["konum"] == "Ofis"
    assert gorev["link"] == "https://example.com"
    assert gorev["teslim_tipi"] == "esnek"
    assert gorev["kesin_bitis"] is None


def test_gorev_kesin_bitis_serilestirilir(test_db, test_user_id):
    create_task(test_user_id, "Kesin görev", teslim_tipi="kesin", kesin_bitis=datetime(2026, 8, 1, 14, 30))

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    gorev = yedek["gorevler"][0]
    assert gorev["teslim_tipi"] == "kesin"
    assert gorev["kesin_bitis"] == "2026-08-01T14:30:00"


def test_etkinlik_ve_plan_kaydi_dahil_edilir(test_db, test_user_id):
    _etkinlik_ekle(test_user_id)
    _plan_kaydi_ekle(test_user_id)

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    assert len(yedek["takvim_etkinlikleri"]) == 1
    assert yedek["takvim_etkinlikleri"][0]["google_id"] == "g1"
    assert len(yedek["plan_kayitlari"]) == 1
    assert yedek["plan_kayitlari"][0]["gun"] == "2026-07-10"


def test_profil_dahil_edilir(test_db, test_user_id):
    profil_kaydet(test_user_id, "Ece Gürbüz", "ece@planla.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    assert yedek["profil"]["ad_soyad"] == "Ece Gürbüz"
    assert yedek["profil"]["verimli_baslangic"] == "07:00:00"


def test_baska_kullanicinin_verisi_disa_aktarilmaz(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_export", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    create_task(diger_id, "Diğer kullanıcının görevi")

    yedek = export_service.tum_veriyi_disa_aktar(test_user_id)

    assert yedek["gorevler"] == []
