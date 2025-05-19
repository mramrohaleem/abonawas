# modules/downloader.py
import asyncio
import hashlib
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Union

from imageio_ffmpeg import get_ffmpeg_exe
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from modules.logger_config import setup_logger

Media = Dict[str, str]
MediaOrPlaylist = Union[Media, List[Media]]


class Downloader:
    """
    تنزيل صوتيات مع:
    • كاش باسم sha256(url) لمنع التنزيل المكرّر
    • تنظيف تلقائى: 3 أيام للملفات الفردية، 10 أيام لملفات قوائم التشغيل
    • تنزيل متوازٍ (يُستخدم من Player)
    """
    SINGLE_TTL = timedelta(days=3)
    PLAYLIST_TTL = timedelta(days=10)

    def __init__(self, logger=None, download_dir: str = "downloads"):
        self.logger = logger or setup_logger(__name__)
        self.dir = Path(download_dir)
        self.dir.mkdir(exist_ok=True)
        self.ffmpeg_exe = get_ffmpeg_exe()

        # تنظيف قديم عند الإقلاع
        asyncio.create_task(self._cleanup())

    # ---------- واجهة عامّة ---------- #
    async def download(self, url: str) -> MediaOrPlaylist:
        """تنزيل الملف إن لم يكن فى الكاش."""
        info = await asyncio.to_thread(self._extract, url)
        if info.get("_type") == "playlist":
            return [self._build_media(e, is_playlist=True) for e in info["entries"]]
        return self._build_media(info, is_playlist=False)

    # ---------- داخلى ---------- #
    # -- التنزيل الفعلى --
    def _extract(self, url: str) -> dict:
        ydl_opts = {
            "quiet": True,
            "format": "bestaudio/best",
            "ffmpeg_location": self.ffmpeg_exe,
            "outtmpl": str(self.dir / "%(id)s.%(ext)s"),
            "cachedir": False,
            "postprocessors": [{"key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192"}],
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except DownloadError as exc:
            self.logger.error(f"yt-dlp error: {exc}", exc_info=True)
            raise RuntimeError("المقطع غير متاح أو محجوب")

    # -- كاش --
    def _hash_name(self, url: str, suffix: str = ".mp3") -> Path:
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.dir / f"{h}{suffix}"

    def _build_media(self, info: dict, *, is_playlist: bool) -> Media:
        url = info.get("original_url") or info.get("webpage_url")
        path = self._hash_name(url)

        # إذا كان فى الكاش – لا تلمس
        if not path.exists():
            src_path = self._choose_audio_path(info)
            os.replace(src_path, path)

        # تحديث الـmtime ليساعد فى التنظيف
        os.utime(path, None)

        return {
            "url": url,
            "title": info.get("title") or "—",
            "path": str(path),
            "is_playlist_item": "1" if is_playlist else "0"
        }

    def _choose_audio_path(self, info: dict) -> str:
        path = info.get("requested_downloads", [{}])[0].get("filepath")
        if path:
            return path
        raise RuntimeError("تعذّر إيجاد الملف الصوتى بعد التنزيل")

    # -- تنظيف تلقائى --
    async def _cleanup(self):
        while True:
            now = datetime.utcnow()
            for p in self.dir.iterdir():
                if not p.is_file():
                    continue
                age = now - datetime.utcfromtimestamp(p.stat().st_mtime)
                ttl = self.PLAYLIST_TTL if ".pl" in p.stem else self.SINGLE_TTL
                if age > ttl:
                    try:
                        p.unlink()
                    except Exception:
                        pass
            await asyncio.sleep(24 * 3600)   # مرة يوميًا
