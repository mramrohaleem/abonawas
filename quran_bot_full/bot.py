
import os, asyncio, discord
from discord.ext import commands
from imageio_ffmpeg import get_ffmpeg_exe
from modules.logger_config import setup_logger

logger = setup_logger("quran_bot")
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states   = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # direct add_cog
        from cogs.player import Player
        from cogs.azkar  import AzkarCog
        await self.add_cog(Player(self))
        await self.add_cog(AzkarCog(self))

        # load other ext
        await self.load_extension("cogs.help")

        await self.tree.sync()
        logger.info("✅ Slash commands synced")

    async def on_ready(self):
        logger.info(f"🟢 Logged in as {self.user} ({self.user.id})")

async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN not set.")
        return
    bot = QuranBot()
    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
