# bot.py
import os, asyncio, logging, discord
from discord.ext import commands
from imageio_ffmpeg import get_ffmpeg_exe
from modules.logger_config import setup_logger

logger = setup_logger()
FFMPEG_EXE = get_ffmpeg_exe()
logger.info(f"✔ Using ffmpeg: {FFMPEG_EXE}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = FFMPEG_EXE   # يقرأه الـ cogs

    async def setup_hook(self):
        # تحميل الـ cogs ديناميكياً
        for ext in ("cogs.player",):
            await self.load_extension(ext)

        await self.tree.sync()
        logger.info("✅ Slash commands synced")

    async def on_ready(self):
        logger.info(f"🟢 Logged in as {self.user} ({self.user.id})")

async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN not set")
        return
    await QuranBot().start(token)

if __name__ == "__main__":
    asyncio.run(main())
