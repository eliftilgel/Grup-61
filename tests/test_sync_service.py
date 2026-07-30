"""sync_service.upsert_events için birim testleri — Google API'si gerekmez."""

from core.services.sync_service import create_event_everywhere, list_events, upsert_events
from core.services.task_service import create_task, list_tasks


def ornek(gid: str, updated: str = "2026-01-01T10:00:00Z", **degisiklik) -> dict:
    e = {
        "google_id": gid,
        "title": "Toplantı",
        "description": "",
        "start": "2026-07-10T09:00:00+03:00",
        "end": "2026-07-10T10:00:00+03:00",
        "updated": updated,
    }
    e.update(degisiklik)
    return e


def test_yeni_etkinlik_eklenir(test_db, test_user_id):
    sonuc = upsert_events(test_user_id, [ornek("abc1"), ornek("abc2")])
    assert sonuc == {"eklendi": 2, "guncellendi": 0, "silindi": 0}


def test_ayni_liste_ikinci_kez_kopya_uretmez(test_db, test_user_id):
    upsert_events(test_user_id, [ornek("abc1")])
    sonuc = upsert_events(test_user_id, [ornek("abc1")])
    assert sonuc == {"eklendi": 0, "guncellendi": 0, "silindi": 0}


def test_degisen_etkinlik_guncellenir(test_db, test_user_id):
    upsert_events(test_user_id, [ornek("abc1")])
    yeni = ornek("abc1", updated="2026-01-02T08:00:00Z", title="Toplantı (yeni saat)")
    sonuc = upsert_events(test_user_id, [yeni])
    assert sonuc["guncellendi"] == 1


def test_gelmeyen_etkinlik_silinir(test_db, test_user_id):
    upsert_events(test_user_id, [ornek("abc1"), ornek("abc2")])
    sonuc = upsert_events(test_user_id, [ornek("abc1")])
    assert sonuc["silindi"] == 1


def test_gorevler_etkinlik_senkronundan_etkilenmez(test_db, test_user_id):
    """upsert_events'in 'artık gelmeyeni sil' mantığı görev satırlarına dokunmamalı."""
    gorev = create_task(test_user_id, "Etkilenmemesi gereken görev")

    upsert_events(test_user_id, [ornek("abc1")])
    upsert_events(test_user_id, [])  # hiçbir etkinlik gelmiyor: sadece etkinlikler silinmeli

    kalan_gorevler = list_tasks(test_user_id)
    assert [g.id for g in kalan_gorevler] == [gorev.id]


def test_create_event_everywhere_konum_yerel_kopyaya_yazilir(test_db, test_user_id, monkeypatch):
    from core.services import calendar_service

    def sahte_create_event(title, start_iso, end_iso, description="", location=""):
        assert location == "Ofis"
        return {"id": "sahte_google_id", "updated": "2026-01-01T00:00:00Z"}

    monkeypatch.setattr(calendar_service, "create_event", sahte_create_event)

    create_event_everywhere(
        test_user_id, "Toplantı", "2026-07-10T09:00:00+03:00", "2026-07-10T10:00:00+03:00",
        description="", konum="Ofis",
    )

    etkinlikler = list_events(test_user_id)
    assert etkinlikler[0].konum == "Ofis"


def test_iki_kullanicinin_ayni_google_id_ile_etkinligi_olabilir(test_db, test_user_id):
    from core.models import User

    with test_db() as session:
        diger = User(username="diger_sync", password_hash="x", is_admin=False)
        session.add(diger)
        session.commit()
        diger_id = diger.id

    sonuc1 = upsert_events(test_user_id, [ornek("ayni_id")])
    sonuc2 = upsert_events(diger_id, [ornek("ayni_id")])

    assert sonuc1 == {"eklendi": 1, "guncellendi": 0, "silindi": 0}
    assert sonuc2 == {"eklendi": 1, "guncellendi": 0, "silindi": 0}
