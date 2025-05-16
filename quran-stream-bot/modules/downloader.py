import os
import asyncio
import aiohttp
from pathlib import Path
from yt_dlp import YoutubeDL, DownloadError
from imageio_ffmpeg import get_ffmpeg_exe  # المسار المدمج لـ FFmpeg

FFMPEG_PATH = get_ffmpeg_exe()

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ملف الكوكيز (أو عيِّن متغيّر YT_COOKIES)
COOKIE_FILE = Path(os.getenv("YT_COOKIES", "cookies.txt"))

class Downloader:
    """
    تنزيل مباشر .mp3 أو استخراج الصوت من YouTube/قائمة تشغيل.
    - عند تمرير رابط Playlist: تُعاد قائمة URLs للعناصر الفرعية.
    - عند تمرير فيديو/MP3 مفرد: يُعاد الـ path المحلي للـ MP3.
    """
    def __init__(self, logger):
        self.logger = logger

    async def download(self, url: str):
        """واجهة استدعاء من بقية الكود."""
        if url.lower().endswith(".mp3"):
            return await self._download_http(url)
        return await asyncio.to_thread(self._download_with_ytdlp, url)

    # ---------- تنزيل HTTP ----------
    async def _download_http(self, url: str) -> str:
        filename = url.split("/")[-1].split("?")[0] or "file.mp3"
        path = DOWNLOADS_DIR / filename
        if path.exists():
            self.logger.info(f"🎧 موجود بالكاش: {path}")
            return str(path)

        self.logger.info(f"⬇️ تنزيل مباشر: {url}")
        async with aiohttp.ClientSession() as s, s.get(url) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                while chunk := await r.content.read(16 * 1024):
                    f.write(chunk)
        self.logger.info(f"✅ تم الحفظ: {path}")
        return str(path)

    # ---------- yt-dlp ----------
    def _download_with_ytdlp(self, url: str):
        """
        قد يُعيد:
        • List[str]  → عند تمرير رابط Playlist (عناصرها كروابط فيديو)
        • str        → مسار ملف MP3 محمَّل لجهاز واحد
        """
        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "ffmpeg_location": FFMPEG_PATH,
        }

        # --- إذا كان الرابط Playlist (يحتوي "list=" وليس "watch?") ---
        if "list=" in url and "watch?" not in url:
            opts = {**base_opts, "extract_flat": "in_playlist", "skip_download": True}
            with YoutubeDL(opts) as ydl:
                info   = ydl.extract_info(url, download=False)
                videos = [e["url"] for e in info["entries"]]
                self.logger.info(f"📜 قائمة تشغيل بها {len(videos)} مقطعاً.")
                return videos    # يرسلها إلى الطابور

        # --- فيديو مفرد ---
        ytdl_opts = {
            **base_opts,
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "noplaylist": True,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        if COOKIE_FILE.exists():
            ytdl_opts["cookiefile"] = str(COOKIE_FILE)
            self.logger.info("🍪 يستخدم cookies.txt")

        try:
            with YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                mp3  = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
                self.logger.info(f"🎵 تم التنزيل: {mp3}")
                return str(mp3)
        except DownloadError as e:
            self.logger.error(f"❌ yt-dlp: {e}")
            raise RuntimeError("فشل تحميل الرابط (تأكد من الكوكيز والشبكة).") from e
