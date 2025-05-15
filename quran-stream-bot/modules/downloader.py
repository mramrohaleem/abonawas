import aiohttp
from pathlib import Path
from logging import Logger

class Downloader:
    """
    Downloads MP3 files asynchronously and caches them locally.
    """
    def __init__(self, logger: Logger, download_dir: str = "downloads"):
        self.logger = logger
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)

    async def download(self, url: str) -> str:
        """
        Downloads the file at `url` and returns the local filepath.
        """
        filename = url.split("/")[-1]
        dest = self.download_dir / filename

        if dest.exists():
            self.logger.info(f"Cache hit: {dest}")
            return str(dest)

        self.logger.info(f"Downloading: {url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    with open(dest, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024):
                            f.write(chunk)
                            self.logger.debug(f"Wrote chunk ({len(chunk)} bytes)")
            self.logger.info(f"Downloaded to: {dest}")
            return str(dest)
        except Exception as e:
            self.logger.error(f"Download failed: {e}", exc_info=True)
            raise
