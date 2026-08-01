"""ai_advisor için birim testleri — Gemini istemcisi her zaman mock'lanır, gerçek API çağrılmaz."""

from datetime import date, time
from unittest.mock import MagicMock

from core.models import PlanKaydi, Profil
from core.services import ai_advisor
from core.services.planning_service import plan_olustur
from core.services.task_service import create_task

VARSAYILAN_PROFIL = Profil(
    ad_soyad="Test",
    verimli_baslangic=time(7, 0),
    verimli_bitis=time(13, 0),
    uyku_baslangic=time(23, 0),
    uyku_bitis=time(7, 0),
    gunluk_hedef=5,
)


def _plan_kur(test_user_id):
    gun = date(2026, 7, 6)
    gorev = create_task(test_user_id, "Rapor yaz", priority=2, duration_minutes=30, due_date=gun)
    kayit = plan_olustur(test_user_id, gun, [gorev], [], VARSAYILAN_PROFIL)
    return kayit


# --- (a) API anahtarı yoksa: hiçbir şey değişmez / kural tabanlı metne düşülür ---------------


def test_anahtar_yoksa_gerekceler_degismez(test_db, test_user_id, monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", None)
    kayit = _plan_kur(test_user_id)
    orijinal_gerekce = kayit.dilimler[0]["gerekce"]

    ai_advisor.gerekceleri_zenginlestir(kayit.id, VARSAYILAN_PROFIL)

    with test_db() as session:
        guncel = session.get(PlanKaydi, kayit.id)
        assert guncel.dilimler[0]["gerekce"] == orijinal_gerekce


def test_anahtar_yoksa_analiz_metni_kural_tabanli(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", None)
    metin = ai_advisor.analiz_metni_uret({"07–10": 80, "10–13": 95, "13–16": 90, "16–19": 85, "19–22": 100})
    assert "07–10" in metin


def test_anahtar_yoksa_yorum_kural_tabanli(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", None)
    assert "Harika" in ai_advisor.yorum_uret(100, 3, 3)


# --- (b) Gemini çağrısı patlarsa: sessizce kural tabanlı sonuca düşülür ----------------------


def _patlayan_client():
    raise RuntimeError("boom")


def test_gemini_hata_verirse_gerekceler_korunur(test_db, test_user_id, monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    monkeypatch.setattr(ai_advisor, "_client", _patlayan_client)
    kayit = _plan_kur(test_user_id)
    orijinal_gerekce = kayit.dilimler[0]["gerekce"]

    ai_advisor.gerekceleri_zenginlestir(kayit.id, VARSAYILAN_PROFIL)  # raise etmemeli

    with test_db() as session:
        guncel = session.get(PlanKaydi, kayit.id)
        assert guncel.dilimler[0]["gerekce"] == orijinal_gerekce


def test_gemini_hata_verirse_analiz_metni_kural_tabanli(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    monkeypatch.setattr(ai_advisor, "_client", _patlayan_client)
    metin = ai_advisor.analiz_metni_uret({"07–10": 95, "10–13": 10, "13–16": 90, "16–19": 85, "19–22": 100})
    assert "10–13" in metin


def test_gemini_hata_verirse_yorum_kural_tabanli(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    monkeypatch.setattr(ai_advisor, "_client", _patlayan_client)
    assert "Harika" in ai_advisor.yorum_uret(100, 2, 2)


# --- (c) Başarılı mock yanıt: metin gerçekten Gemini çıktısına değişir -----------------------


def test_basarili_gemini_yaniti_gerekceleri_gunceller(test_db, test_user_id, monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    kayit = _plan_kur(test_user_id)
    task_id = kayit.dilimler[0]["task_id"]

    sahte_yanit = MagicMock()
    sahte_yanit.text = '{"gerekceler": [{"task_id": %d, "gerekce": "Gemini gerekcesi"}]}' % task_id
    sahte_client = MagicMock()
    sahte_client.models.generate_content.return_value = sahte_yanit
    monkeypatch.setattr(ai_advisor, "_client", lambda: sahte_client)

    ai_advisor.gerekceleri_zenginlestir(kayit.id, VARSAYILAN_PROFIL)

    with test_db() as session:
        guncel = session.get(PlanKaydi, kayit.id)
        assert guncel.dilimler[0]["gerekce"] == "Gemini gerekcesi"

    cagri = sahte_client.models.generate_content.call_args
    assert cagri.kwargs["config"].response_mime_type == "application/json"
    assert cagri.kwargs["config"].response_schema is ai_advisor._GerekceYaniti


def test_basarili_gemini_yaniti_analiz_metni_degisir(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    sahte_yanit = MagicMock()
    sahte_yanit.text = "Gemini'den gelen analiz metni."
    sahte_client = MagicMock()
    sahte_client.models.generate_content.return_value = sahte_yanit
    monkeypatch.setattr(ai_advisor, "_client", lambda: sahte_client)

    metin = ai_advisor.analiz_metni_uret({"07–10": 50, "10–13": 50, "13–16": 0, "16–19": 0, "19–22": 0})

    assert metin == "Gemini'den gelen analiz metni."


def test_basarili_gemini_yaniti_yorum_degisir(monkeypatch):
    monkeypatch.setattr(ai_advisor.settings, "gemini_api_key", "sahte-anahtar")
    sahte_yanit = MagicMock()
    sahte_yanit.text = "Gemini'den gelen gün sonu yorumu."
    sahte_client = MagicMock()
    sahte_client.models.generate_content.return_value = sahte_yanit
    monkeypatch.setattr(ai_advisor, "_client", lambda: sahte_client)

    assert ai_advisor.yorum_uret(60, 5, 3) == "Gemini'den gelen gün sonu yorumu."
