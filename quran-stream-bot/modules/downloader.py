import os
import asyncio
import aiohttp
from pathlib import Path
from yt_dlp import YoutubeDL, DownloadError
from imageio_ffmpeg import get_ffmpeg_exe

FFMPEG_PATH  = get_ffmpeg_exe()
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

COOKIE_FILE = Path(os.getenv("YT_COOKIES", "cookies.txt"))

class Downloader:
    """ينزّل روابط MP3 مباشرة أو يحوّل فيديو/قائمة تشغيل YouTube إلى MP3"""
    def __init__(self, logger):
        self.logger = logger

    async def download(self, url: str):
        if url.lower().endswith(".mp3"):
            return await self._http(url)
        return await asyncio.to_thread(self._ytdlp, url)

    async def _http(self, url: str) -> str:
        fn   = url.split("/")[-1].split("?")[0] or "file.mp3"
        path = DOWNLOADS_DIR / fn
        if path.exists():
            self.logger.info(f"🎧 كاش: {path}")
            return str(path)

        async with aiohttp.ClientSession() as s, s.get(url) as r:
            r.raise_for_status()
            with open(path, "wb") as f:
                while chunk := await r.content.read(16384):
                    f.write(chunk)
        self.logger.info(f"⬇️ حُفِظ: {path}")
        return str(path)

    # --------------- yt-dlp ---------------
    def _ytdlp(self, url: str):
        base = {
            "quiet": True, "no_warnings": True, "geo_bypass": True,
            "ffmpeg_location": FFMPEG_PATH,
        }

        # -------- Playlist؟
        if "list=" in url and "watch?" not in url:
            opts = {**base, "extract_flat": "in_playlist", "skip_download": True}
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                lst  = [{"url": e["url"], "title": e.get("title", '—')} for e in info["entries"]]
                self.logger.info(f"📜 Playlist حجمها {len(lst)}")
                return lst                              # قائمة عناصر

        # -------- فيديو مفرد --------
        opts = {
            **base,
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
                mp3  = Path(ydl.prepare_filename(info)).with_suffix(".mp3")
                return {"path": str(mp3), "title": info.get("title") or mp3.name}
        except DownloadError as e:
            self.logger.error(f"❌ yt-dlp: {e}")
            raise RuntimeError("فشل تحميل الرابط.") from e
