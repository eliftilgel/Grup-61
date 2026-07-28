"""Veri tabanı bağlantısı ve session yönetimi"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.config import settings

engine = create_engine(settings.database_url, echo=settings.sqlalchemy_echo)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    """Tüm modellerin miras alacağı taban sınıf"""

def init_db():
    """Tanımlı tüm tabloları (yoksa) oluşturur."""
    Base.metadata.create_all(engine)