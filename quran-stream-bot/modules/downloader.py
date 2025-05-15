import asyncio
import aiohttp
import os
from pathlib import Path
from yt_dlp import YoutubeDL

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

class Downloader:
    """
    يقوم بتنـزيل رابط MP3 مباشر أو رابط يوتيوب/ساوندكلاود
    ويُرجع المسار المحلي للملف الصوتي.
    """
    def __init__(self, logger):
        self.logger = logger

    async def download(self, url: str) -> str:
        # إذا كان الرابط ينتهي بـ mp3 مباشرةً يعطي تحميل بسيط
        if url.lower().endswith(".mp3"):
            return await self._download_http(url)

        # خلاف ذلك جرّب yt-dlp لاستخراج الصوت
        return await asyncio.to_thread(self._download_with_ytdlp, url)

    async def _download_http(self, url: str) -> str:
        filename = url.split("/")[-1].split("?")[0]
        local_path = DOWNLOADS_DIR / filename
        if local_path.exists():
            self.logger.info(f"Cache hit: {local_path}")
            return str(local_path)

        self.logger.info(f"Downloading direct MP3: {url}")
        async with aiohttp.ClientSession() as sess, sess.get(url) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                while chunk := await resp.content.read(1024 * 16):
                    f.write(chunk)
        self.logger.info(f"Saved to {local_path}")
        return str(local_path)

    # هذه الدالة تُشغَّل في خيط منفصل عبر asyncio.to_thread
    def _download_with_ytdlp(self, url: str) -> str:
        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            "extractaudio": True,
            "audioformat": "mp3",
            # "cookiefile": "cookies.txt",  # فعّل عند الحاجة
        }
        with YoutubeDL(ytdl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = ydl.prepare_filename(info)
            # yt-dlp قد يعطي امتداد webm أو m4a؛ نحوله ل‎.mp3 إذا لزم
            if not path.endswith(".mp3") and os.path.exists(path):
                new_path = os.path.splitext(path)[0] + ".mp3"
                os.rename(path, new_path)
                path = new_path
            self.logger.info(f"yt-dlp downloaded: {path}")
            return path
