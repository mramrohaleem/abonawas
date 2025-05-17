import os
import asyncio
import aiohttp
from pathlib import Path
from yt_dlp import YoutubeDL, DownloadError
from imageio_ffmpeg import get_ffmpeg_exe

FFMPEG_PATH   = get_ffmpeg_exe()
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

COOKIE_FILE = Path(os.getenv("YT_COOKIES", "cookies.txt"))

class Downloader:
    """ينزّل MP3 مباشر أو يستخرج الصوت من YouTube/Playlist."""
    def __init__(self, logger):
        self.logger = logger

    async def download(self, url: str):
        if url.lower().endswith(".mp3"):
            return await self._http_download(url)
        # yt-dlp قد يستغرق وقتًا، لذا في thread منفصل
        return await asyncio.to_thread(self._ytdlp_download, url)

    async def _http_download(self, url: str) -> dict:
        filename = url.split("/")[-1].split("?")[0] or "file.mp3"
        path = DOWNLOADS_DIR / filename
        if path.exists():
            self.logger.info(f"🎧 موجود في الكاش: {path}")
            return {"path": str(path), "title": path.name}

        self.logger.info(f"⬇️ تنزيل مباشر: {url}")
        async with aiohttp.ClientSession() as sess, sess.get(url) as resp:
            resp.raise_for_status()
            with open(path, "wb") as f:
                while chunk := await resp.content.read(16*1024):
                    f.write(chunk)
        self.logger.info(f"✅ حُفظ: {path}")
        return {"path": str(path), "title": path.name}

    def _ytdlp_download(self, url: str):
        base_opts = {
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "ffmpeg_location": FFMPEG_PATH,
        }

        # Playlist؟
        if "list=" in url and "watch?" not in url:
            opts = {**base_opts, "extract_flat": "in_playlist", "skip_download": True}
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                lst = [{"url": e["url"], "title": e.get("title", "—")} for e in info["entries"]]
                self.logger.info(f"📜 وجد قائمة تشغيل بحجم {len(lst)}")
                return lst  # قائمة URLs+titles

        # فيديو واحد
        opts = {
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
            opts["cookiefile"] = str(COOKIE_FILE)
            self.logger.info("🍪 يستخدم cookies.txt")

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                mp3_path = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
                title = info.get("title") or mp3_path.name
                self.logger.info(f"🎵 تم تنزيل: {mp3_path}")
                return {"path": str(mp3_path), "title": title}
        except DownloadError as e:
            self.logger.error(f"❌ yt-dlp خطأ: {e}")
            raise RuntimeError("فشل تحميل الرابط.") from e
