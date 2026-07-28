"""logging_config için birim testleri."""

import logging

import core.logging_config as logging_config


def test_setup_logging_dosya_ve_handler_olusturur(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "_kuruldu", False)
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(logging_config, "LOG_FILE", tmp_path / "logs" / "planla.log")

    kok_logger = logging.getLogger()
    onceki_sayisi = len(kok_logger.handlers)

    try:
        logging_config.setup_logging()

        assert (tmp_path / "logs").exists()
        assert len(kok_logger.handlers) == onceki_sayisi + 1
    finally:
        for h in kok_logger.handlers[onceki_sayisi:]:
            kok_logger.removeHandler(h)
            h.close()


def test_setup_logging_iki_kez_cagrilinca_handler_cogalmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(logging_config, "_kuruldu", False)
    monkeypatch.setattr(logging_config, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(logging_config, "LOG_FILE", tmp_path / "logs" / "planla.log")

    kok_logger = logging.getLogger()
    onceki_sayisi = len(kok_logger.handlers)

    try:
        logging_config.setup_logging()
        sayisi_ilk_cagridan_sonra = len(kok_logger.handlers)

        logging_config.setup_logging()

        assert len(kok_logger.handlers) == sayisi_ilk_cagridan_sonra
    finally:
        for h in kok_logger.handlers[onceki_sayisi:]:
            kok_logger.removeHandler(h)
            h.close()
