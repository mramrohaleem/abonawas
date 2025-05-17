# modules/logger_config.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

def setup_logger(name: str | None = None) -> logging.Logger:
    logger = logging.getLogger(name or "quran_bot")
    logger.setLevel(logging.INFO)

    # تدوير الملف: 2 MiB × 3 نسخ احتياطية
    file_handler = RotatingFileHandler(
        LOG_DIR / "quran_bot.log",
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8"
    )
    fmt = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
    file_handler.setFormatter(logging.Formatter(fmt))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(fmt))

    logger.handlers.clear()
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)

    return logger
