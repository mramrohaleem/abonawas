import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

logger = setup_logger()

ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # 1) حمّل كوج الـ Player
        await self.load_extension("cogs.player")
        # 2) سجّل view بعد انتهاء التحميل
        player = self.get_cog("Player")
        if player:
            self.add_view(player.controls)
            logger.info("Registered persistent PlayerControls view")

async def main():
    bot = QuranBot()

    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set.")
        return

    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
