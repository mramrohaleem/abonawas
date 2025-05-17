# modules/downloader.py
import hashlib, asyncio, shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any
from yt_dlp import YoutubeDL
from imageio_ffmpeg import get_ffmpeg_exe

CACHE_DIR   = Path("downloads"); CACHE_DIR.mkdir(exist_ok=True)
RETENTION_DAYS = 10              # احذف الملفات الأقدم من هذا العدد
PARALLEL_DOWNLOADS = 2           # أقصى تنزيلات متزامنة

class Downloader:
    """تنزيل mp3 مع كاش مبني على SHA-256(link)."""

    _sem = asyncio.Semaphore(PARALLEL_DOWNLOADS)

    def __init__(self, logger):
        self.logger = logger
        self.ffmpeg = get_ffmpeg_exe()
        asyncio.create_task(self._cleanup_old())

    # -------------------------------------------- #

    async def download(self, url: str) -> dict[str, Any]:
        h = hashlib.sha256(url.encode()).hexdigest()[:16]
        mp3_path = CACHE_DIR / f"{h}.mp3"
        if mp3_path.exists():
            self.logger.info(f"🎵 استخدم الكاش: {mp3_path}")
            return {"url": url, "path": str(mp3_path), "title": mp3_path.stem}

        async with self._sem:           # حدّ التوازي
            return await asyncio.to_thread(self._ydl_fetch, url, mp3_path)

    # -------------------------------------------- #

    def _ydl_fetch(self, url: str, mp3_path: Path):
        opts = {
            "format": "bestaudio/best",
            "outtmpl": str(mp3_path.with_suffix(".%(ext)s")),
            "quiet":   True,
            "ffmpeg_location": self.ffmpeg,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title") or mp3_path.stem
            # yt-dl سيحفظ باسم temp.ext ثم يُعيد تسميته؛ نتأكّد من الاسم النهائي
            real_file = next(mp3_path.parent.glob(f"{mp3_path.stem}.*"))
            if real_file.suffix != ".mp3":
                real_file.rename(mp3_path)
            self.logger.info(f"🎵 تم تنزيل: {mp3_path}")
            return {"url": url, "path": str(mp3_path), "title": title}
        except Exception as e:
            self.logger.error(f"yt-dlp error: {e}", exc_info=True)
            raise

    # -------------------------------------------- #

    async def _cleanup_old(self):
        """يحذف الملفات الأقدم من RETENTION_DAYS مرة واحدة عند الإقلاع."""
        threshold = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
        removed = 0
        for f in CACHE_DIR.glob("*.mp3"):
            if datetime.utcfromtimestamp(f.stat().st_mtime) < threshold:
                try:
                    f.unlink(); removed += 1
                except OSError: pass
        if removed:
            self.logger.info(f"🧹 حُذف {removed} ملفًا قديمًا من الكاش")
