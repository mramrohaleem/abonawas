import os
import asyncio
import aiohttp
from pathlib import Path
from yt_dlp import YoutubeDL, DownloadError

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


class Downloader:
    """
    يتولّى تنزيل الروابط:
      • إن كان الرابط ‎.mp3 مباشر ⇒ تنزيل HTTP بسيط
      • وإلا يستعمل yt-dlp لاستخراج الصوت (MP3) من YouTube أو SoundCloud
    """
    def __init__(self, logger):
        self.logger = logger

    async def download(self, url: str) -> str:
        if url.lower().endswith(".mp3"):
            return await self._download_http(url)

        # تشغيل yt-dlp في خيط منفصل تفادياً لحجب حدث اللوب
        return await asyncio.to_thread(self._download_with_ytdlp, url)

    # ---------- تنزيل مباشر ----------
    async def _download_http(self, url: str) -> str:
        filename = url.split("/")[-1].split("?")[0] or "file.mp3"
        path = DOWNLOADS_DIR / filename
        if path.exists():
            self.logger.info(f"🎧 تم إيجاد الملف في الكاش: {path}")
            return str(path)

        self.logger.info(f"⬇️ تنزيل مباشر: {url}")
        async with aiohttp.ClientSession() as sess, sess.get(url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                while chunk := await resp.content.read(16 * 1024):
                    f.write(chunk)
        self.logger.info(f"✅ حُفِظ في: {path}")
        return str(path)

    # ---------- تنزيل بواسطة yt-dlp ----------
    def _download_with_ytdlp(self, url: str) -> str:
        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            # تحويل تلقائي إلى MP3 بالجودة 192 kbps
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
            # "cookiefile": "cookies.txt",  # فعّلها إذا احتجت ملفات كوكيز
        }
        try:
            with YoutubeDL(ytdl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                base = ydl.prepare_filename(info)
                mp3_path = os.path.splitext(base)[0] + ".mp3"
                self.logger.info(f"🎵 yt-dlp أنجز: {mp3_path}")
                return mp3_path
        except DownloadError as e:
            self.logger.error(f"❌ yt-dlp خطأ: {e}")
            raise
