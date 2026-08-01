"""Test kurulumu: her test kendi geçici veritabanını kullanır."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from core.database import Base
from core.models import User


@pytest.fixture()
def test_db(tmp_path, monkeypatch):
    """Geçici bir SQLite dosyası oluşturur ve servisleri ona yönlendirir."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")

    @event.listens_for(engine, "connect")
    def _fk_ac(dbapi_connection, connection_record):
        imlec = dbapi_connection.cursor()
        imlec.execute("PRAGMA foreign_keys=ON")
        imlec.close()

    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr("core.services.task_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.sync_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.profil_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.planning_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.report_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.export_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.user_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.rutin_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.haftalik_blok_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.enerji_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.degerlendirme_service.SessionLocal", TestSession)
    monkeypatch.setattr("core.services.ai_advisor.SessionLocal", TestSession)
    return TestSession


@pytest.fixture()
def test_user_id(test_db) -> int:
    """test_db üzerinde bir kullanıcı oluşturup id'sini döner."""
    with test_db() as session:
        user = User(username="test_kullanici", password_hash="x", is_admin=False)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user.id
