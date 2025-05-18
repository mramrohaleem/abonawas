# modules/downloader.py
import hashlib
import os
from pathlib import Path
from typing import Dict, List, Union

from imageio_ffmpeg import get_ffmpeg_exe
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from modules.logger_config import setup_logger

Media = Dict[str, str]              # {"url", "title", "path"}
MediaOrPlaylist = Union[Media, List[Media]]


class Downloader:
    """
    أداة تنزيل صوت (فيديوهات YouTube / Facebook / …) باستخدام yt-dlp.
    ترجع dict واحدة أو قائمة dicts عند قوائم التشغيل.
    """
    def __init__(self, logger=None, download_dir: str = "downloads"):
        self.logger = logger or setup_logger(__name__)
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(exist_ok=True)
        self.ffmpeg_exe = get_ffmpeg_exe()

    # ---------- واجهة عامّة ----------
    async def download(self, url: str) -> MediaOrPlaylist:
        try:
            info = self._extract(url)
        except RuntimeError:
            raise                                          # أعد تمرير الخطأ إلى Player

        if info.get("_type") == "playlist":
            return [self._build_media(e) for e in info["entries"]]

        return self._build_media(info)

    # ---------- داخلي ----------
    def _extract(self, url: str) -> dict:
        ydl_opts = {
            "quiet": True,
            "format": "bestaudio/best",
            "ffmpeg_location": self.ffmpeg_exe,
            "outtmpl": str(self.download_dir / "%(id)s.%(ext)s"),
            "cachedir": False,
            # يسمح بإسقاط الفيديو إن كان Audio فقط غير متاح
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}],
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except DownloadError as exc:
            self.logger.error(f"yt-dlp error: {exc}", exc_info=True)
            raise RuntimeError("المقطع غير متاح أو محجوب")

    # اختيار الملفّ الصوتي الناتج
    def _choose_audio_path(self, info: dict) -> str:
        # yt-dlp يضع المسار في requested_downloads[0]
        path = info.get("requested_downloads", [{}])[0].get("filepath")
        if path:
            return path
        # fallback: ابحث في مجلد التنزيل باسم id.*‎
        stem = info["id"]
        for ext in ("mp3", "m4a", "webm", "opus"):
            p = self.download_dir / f"{stem}.{ext}"
            if p.exists():
                return str(p)
        raise RuntimeError("تعذّر إيجاد الملف الصوتي بعد التنزيل")

    def _build_media(self, info: dict) -> Media:
        return {
            "url": info.get("original_url") or info.get("webpage_url"),
            "title": info.get("title") or "—",
            "path": self._choose_audio_path(info)
        }
