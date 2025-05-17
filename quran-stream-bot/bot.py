# bot.py
import os, asyncio, discord
from discord.ext import commands
from imageio_ffmpeg import get_ffmpeg_exe
from modules.logger_config import setup_logger
from modules.downloader import clean_old
from cogs.player import Player

logger = setup_logger()

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = get_ffmpeg_exe()

    async def setup_hook(self):
        clean_old(days=7)                 # ← تنظيف تلقائى
        await self.add_cog(Player(self))
        await self.tree.sync()
        logger.info("✅ Slash commands synced")

    async def on_ready(self):
        logger.info(f"🟢 Logged in as {self.user} ({self.user.id})")

async def main():
    bot = QuranBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN غير مضبوط.")
        return
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
