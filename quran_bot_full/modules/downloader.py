
import asyncio, os, hashlib
from pathlib import Path
from typing import Dict, List, Union
from imageio_ffmpeg import get_ffmpeg_exe
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from modules.logger_config import setup_logger

Media = Dict[str,str]
MediaOrPlaylist = Union[Media, List[Media]]

class Downloader:
    SINGLE_TTL_SEC = 3*24*3600
    PLAYLIST_TTL_SEC = 10*24*3600

    def __init__(self, logger=None, download_dir="downloads"):
        self.log = logger or setup_logger(__name__)
        self.dir = Path(download_dir)
        self.dir.mkdir(exist_ok=True)
        self.ffmpeg_exe = get_ffmpeg_exe()
        asyncio.create_task(self._cleanup())

    async def download(self, url:str) -> MediaOrPlaylist:
        info = await asyncio.to_thread(self._extract, url)
        if info.get("_type") == "playlist":
            return [self._build_media(e, pl=True) for e in info["entries"]]
        return self._build_media(info, pl=False)

    def _extract(self, url):
        ydl_opts = {
            "quiet": True,
            "format": "bestaudio/best",
            "ffmpeg_location": self.ffmpeg_exe,
            "outtmpl": str(self.dir/ "%(id)s.%(ext)s"),
            "cachedir": False,
            "postprocessors": [{"key":"FFmpegExtractAudio","preferredcodec":"mp3"}],
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(url, download=True)
        except DownloadError as e:
            self.log.error(f"yt-dlp error: {e}")
            raise RuntimeError("المقطع غير متاح أو محجوب")

    def _hash_path(self, url):
        h = hashlib.sha256(url.encode()).hexdigest()
        return self.dir/f"{h}.mp3"

    def _build_media(self, info, *, pl:bool):
        url = info.get("original_url") or info.get("webpage_url")
        path = self._hash_path(url)
        if not path.exists():
            src = info.get("requested_downloads", [{}])[0].get("filepath")
            if not src or not os.path.exists(src):
                raise RuntimeError("تنزيل فاشل")
            os.replace(src, path)
        os.utime(path, None)
        return {"url":url, "title":info.get("title") or "—", "path":str(path)}

    async def _cleanup(self):
        import time
        while True:
            now = time.time()
            for p in self.dir.iterdir():
                if p.is_file():
                    age = now - p.stat().st_mtime
                    ttl = self.SINGLE_TTL_SEC
                    if p.stem.endswith(".pl"):
                        ttl = self.PLAYLIST_TTL_SEC
                    if age > ttl:
                        try: p.unlink()
                        except: pass
            await asyncio.sleep(24*3600)
