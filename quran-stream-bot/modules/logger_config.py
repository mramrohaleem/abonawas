# modules/logger_config.py
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

import requests

WEBHOOK_URL = os.getenv("DISCORD_ERROR_WEBHOOK")  # اختياري: أرسِل الأخطاء لقناة ديسكورد


def setup_logger(name: str = "quran_bot") -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:                    # منع الازدواج عند الاستيراد المتكرّر
        return log

    log.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # ---- stdout ----
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    log.addHandler(sh)

    # ---- ملف دوّار (5 MB × 3) ----
    fh = RotatingFileHandler("bot.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    fh.setFormatter(formatter)
    log.addHandler(fh)

    # ---- Webhook للأخطاء (اختياري) ----
    if WEBHOOK_URL:
        log.addHandler(_WebhookHandler(WEBHOOK_URL))

    return log


class _WebhookHandler(logging.Handler):
    def __init__(self, url: str):
        super().__init__(level=logging.ERROR)
        self.url = url

    def emit(self, record: logging.LogRecord):
        try:
            if record.exc_info:
                txt = "".join(traceback.format_exception(*record.exc_info))
            else:
                txt = record.getMessage()
            payload = {"content": f"⚠️ **{record.levelname}**\n```{txt[:1900]}```"}
            requests.post(self.url, json=payload, timeout=5)
        except Exception:
            pass  # لا نريد إثارة خطأ داخل مسجّل الأخطاء نفسه
