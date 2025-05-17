# modules/downloader.py
import asyncio, hashlib, os, time
from pathlib import Path
from typing import List, Dict, Union
from yt_dlp import YoutubeDL, DownloadError
from .logger_config import setup_logger

DOWNLOAD_DIR = Path("downloads")
DOWNLOAD_DIR.mkdir(exist_ok=True)

logger = setup_logger(__name__)

def _sha(name: str) -> str:
    """مسار الملف باسم SHA-256 للـ URL"""
    return hashlib.sha256(name.encode()).hexdigest() + ".mp3"

def clean_old(days: int = 7) -> None:
    """حذف الملفات الأقدم من عدد الأيام المحدّد."""
    now = time.time()
    limit = days * 86_400
    for p in DOWNLOAD_DIR.glob("*.mp3"):
        if now - p.stat().st_mtime > limit:
            try:
                p.unlink()
                logger.info(f"🗑️ حذف {p.name}")
            except Exception as e:
                logger.warning(f"تعذّر حذف {p}: {e}")

class Downloader:
    """تنزيل (أو إعادة استخدام) ملفّ صوتي."""
    def __init__(self, _logger=None):
        self.log = _logger or logger
        self.ytdl_opts = {
            "quiet": True,
            "format": "bestaudio/best",
            "outtmpl": str(DOWNLOAD_DIR / "%(id)s.%(ext)s"),
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192"}],
            "nocheckcertificate": True,
            "noplaylist": False,
            "cookiefile": "cookies.txt",
        }

    async def download(self, url: str) -> Union[Dict, List[Dict]]:
        """يُعيد dict واحد أو list[dict] لقائمة تشغيل."""
        # اسم الملف بحسب الـ SHA لتجنّب التكرار
        dest = DOWNLOAD_DIR / _sha(url)

        if dest.exists():
            self.log.info(f"♻️ استخدام ملفّ موجود: {dest.name}")
            return {"path": str(dest), "title": dest.stem, "url": url}

        try:
            loop = asyncio.get_event_loop()
            info = await loop.run_in_executor(None, self._yt, url)
        except DownloadError as e:
            self.log.error(f"yt-dlp error: {e}")
            raise

        if isinstance(info, list):      # Playlist
            return info

        # ملفّ واحد
        os.replace(info["filepath"], dest)
        info["path"] = str(dest)
        self.log.info(f"🎵 تم تنزيل: {dest}")

        return info

    # ---------- private ---------- #
    def _yt(self, url: str):
        with YoutubeDL(self.ytdl_opts) as ydl:
            data = ydl.extract_info(url, download=True)

        if "_type" in data and data["_type"] == "playlist":
            res = []
            for entry in data["entries"]:
                res.append({
                    "url": f"https://youtu.be/{entry['id']}",
                    "title": entry.get("title", "—")
                })
            return res

        return {
            "title":    data.get("title", "—"),
            "filepath": ydl.prepare_filename(data),   # قبل التغيير إلى dest
            "url":      url
        }
