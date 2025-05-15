import os
import asyncio
import aiohttp
from pathlib import Path
from yt_dlp import YoutubeDL, DownloadError

# مجلد التنزيلات
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# ملف الكوكيز (إما موجود في الجذر أو يمرَّر عبر متغيّر بيئة YT_COOKIES)
COOKIE_FILE = Path(os.getenv("YT_COOKIES", "cookies.txt"))

class Downloader:
    """
    • إذا كان الرابط ينتهي بـ .mp3 ⇐ تنزيل HTTP عادي.
    • وإلا ⇐ استخدام yt-dlp لاستخراج مقطع الصوت وتحويله إلى ‎.mp3.
    """
    def __init__(self, logger):
        self.logger = logger

    # واجهة الاستعمال من بقية الكود
    async def download(self, url: str) -> str:
        if url.lower().endswith(".mp3"):
            return await self._download_http(url)

        # yt-dlp عمله CPU/IO → ننقله إلى خيط منفصل
        return await asyncio.to_thread(self._download_with_ytdlp, url)

    # ---------- تنزيل مباشر ----------
    async def _download_http(self, url: str) -> str:
        filename = url.split("/")[-1].split("?")[0] or "file.mp3"
        local_path = DOWNLOADS_DIR / filename
        if local_path.exists():
            self.logger.info(f"🎧 ملف موجود مسبقًا: {local_path}")
            return str(local_path)

        self.logger.info(f"⬇️ تنزيل مباشر: {url}")
        async with aiohttp.ClientSession() as sess, sess.get(url) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                while chunk := await resp.content.read(16 * 1024):
                    f.write(chunk)
        self.logger.info(f"✅ تم الحفظ: {local_path}")
        return str(local_path)

    # ---------- yt-dlp ----------
    def _download_with_ytdlp(self, url: str) -> str:
        ytdl_opts = {
            "format": "bestaudio/best",
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "noplaylist": True,
            # تحويل الصوت تلقائيًا إلى mp3 بجودة 192
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }
        if COOKIE_FILE.exists():
            ytdl_opts["cookiefile"] = str(COOKIE_FILE)
            self.logger.info("🍪 يستخدم ملف cookies.txt ليوتيوب")

        try:
            with YoutubeDL(ytdl_opts) as ydl:
                info      = ydl.extract_info(url, download=True)
                base_path = Path(ydl.prepare_filename(info))
                mp3_path  = base_path.with_suffix(".mp3")
                self.logger.info(f"🎵 تم التحميل: {mp3_path}")
                return str(mp3_path)
        except DownloadError as e:
            self.logger.error(f"❌ yt-dlp خطأ: {e}")
            raise RuntimeError("تعذّر تحميل الرابط، تحقق من صلاحية الكوكيز") from e
