# modules/logger_config.py
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOG_DIR = Path("logs"); LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "quran_bot.log"

def setup_logger(name: str = "quran_bot") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # تدوير الملف عند 5 MB (يحتفظ بـ 3 ملفات قديمة)
    file_hdl = RotatingFileHandler(LOG_FILE, maxBytes=5_000_000, backupCount=3,
                                   encoding="utf-8")
    file_hdl.setFormatter(logging.Formatter(
        "%(asctime)s - %(levelname)s - %(name)s - %(message)s"))
    stream_hdl = logging.StreamHandler()

    for h in (file_hdl, stream_hdl):
        h.setLevel(logging.INFO)
        logger.addHandler(h)

    return logger
