import logging
from logging.handlers import RotatingFileHandler

def setup_logger(name: str = "quran_bot") -> logging.Logger:
    """
    Sets up a logger with console and rotating file handler.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    formatter = logging.Formatter(fmt)

    # Console handler (INFO+)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # Rotating file handler (DEBUG+)
    fh = RotatingFileHandler(
        filename="quran_bot.log", maxBytes=5 * 1024 * 1024, backupCount=5
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger
