"""Veri tabanı bağlantısı ve session yönetimi"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = "sqlite:///planner.db"

engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    """Tüm modellerin miras alacağı taban sınıf"""

def init_db():
    """Tanımlı tüm tabloları (yoksa) oluşturur."""
    Base.metadata.create_all(engine)