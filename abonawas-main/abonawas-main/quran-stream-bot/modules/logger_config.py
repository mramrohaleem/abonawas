import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

# تم حذف import requests و Webhook handler

def setup_logger(name: str = "quran_bot") -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:  # منع الازدواج عند الاستيراد المتكرّر
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

    return log

# WebhookHandler تم حذفه كليًا
