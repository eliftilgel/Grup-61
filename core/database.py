"""Veri tabanı bağlantısı ve session yönetimi"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from core.config import settings

engine = create_engine(settings.database_url, echo=settings.sqlalchemy_echo)


@event.listens_for(engine, "connect")
def _sqlite_foreign_keys_ac(dbapi_connection, connection_record):
    """SQLite'ta FK zorlaması varsayılan kapalı — ondelete=CASCADE'in çalışması için açılır."""
    imlec = dbapi_connection.cursor()
    imlec.execute("PRAGMA foreign_keys=ON")
    imlec.close()


SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    """Tüm modellerin miras alacağı taban sınıf"""

def init_db():
    """Tanımlı tüm tabloları (yoksa) oluşturur."""
    Base.metadata.create_all(engine)