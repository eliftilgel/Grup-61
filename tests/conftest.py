"""Test Kurulumu: her test kendi geçici veritabanını kullanır."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.database import Base

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """Geçici bir SQLite dosyası oluşturur ve servisi ona yönlendirir."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine)
    monkeypatch.setattr("core.services.task_service.SessionLocal", TestSession)
    return TestSession()
