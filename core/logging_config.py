"""Uygulama genelinde loglama kurulumu — dönen (rotating) dosya handler'ı, dış servis yok."""

import logging
from logging.handlers import RotatingFileHandler

from core.config import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "flowday.log"

_kuruldu = False


def setup_logging(seviye: int = logging.INFO) -> None:
    """Kök logger'a dönen dosya handler'ı ekler. Birden çok çağrıda handler çoğaltmaz."""
    global _kuruldu
    if _kuruldu:
        return

    LOG_DIR.mkdir(exist_ok=True)

    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    kok_logger = logging.getLogger()
    kok_logger.addHandler(handler)
    kok_logger.setLevel(seviye)

    _kuruldu = True
