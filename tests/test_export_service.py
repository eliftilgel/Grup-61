"""export_service için birim testleri."""

from datetime import date, time

from core.models import CalendarEvent, PlanKaydi
from core.services import export_service
from core.services.profil_service import save as profil_kaydet
from core.services.task_service import create_task


def _etkinlik_ekle():
    with export_service.SessionLocal() as session:
        session.add(CalendarEvent(
            google_id="g1", title="Toplantı", description="", start="2026-07-10T09:00:00",
            end="2026-07-10T10:00:00", updated="2026-07-10T08:00:00",
        ))
        session.commit()


def _plan_kaydi_ekle():
    with export_service.SessionLocal() as session:
        session.add(PlanKaydi(gun=date(2026, 7, 10), dilimler=[], toplam_is_dakika=0, bos_zaman_dakika=0))
        session.commit()


def test_bos_veritabaninda_bos_listeler_doner(test_db):
    yedek = export_service.tum_veriyi_disa_aktar()

    assert yedek["gorevler"] == []
    assert yedek["takvim_etkinlikleri"] == []
    assert yedek["plan_kayitlari"] == []
    assert yedek["profil"] is None
    assert "disa_aktarma_tarihi" in yedek


def test_gorevler_dogru_serilestirilir(test_db):
    create_task("Rapor yaz", priority=3, due_date=date(2026, 7, 10), duration_minutes=60)

    yedek = export_service.tum_veriyi_disa_aktar()

    assert len(yedek["gorevler"]) == 1
    gorev = yedek["gorevler"][0]
    assert gorev["title"] == "Rapor yaz"
    assert gorev["due_date"] == "2026-07-10"
    assert gorev["duration_minutes"] == 60


def test_etkinlik_ve_plan_kaydi_dahil_edilir(test_db):
    _etkinlik_ekle()
    _plan_kaydi_ekle()

    yedek = export_service.tum_veriyi_disa_aktar()

    assert len(yedek["takvim_etkinlikleri"]) == 1
    assert yedek["takvim_etkinlikleri"][0]["google_id"] == "g1"
    assert len(yedek["plan_kayitlari"]) == 1
    assert yedek["plan_kayitlari"][0]["gun"] == "2026-07-10"


def test_profil_dahil_edilir(test_db):
    profil_kaydet("Ece Gürbüz", "ece@planla.app", time(7, 0), time(13, 0), time(23, 0), time(7, 0), 5)

    yedek = export_service.tum_veriyi_disa_aktar()

    assert yedek["profil"]["ad_soyad"] == "Ece Gürbüz"
    assert yedek["profil"]["verimli_baslangic"] == "07:00:00"
