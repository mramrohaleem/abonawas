import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe

# Bot intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

logger = setup_logger()

# تحديد مسار ffmpeg المضمّن
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # اجعل مسار ffmpeg متاحاً للكوج
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # حمّل كوج التشغيل (يحمّل cogs/ui تلقائياً عبر الاستيراد)
        await self.load_extension("cogs.player")

async def main():
    bot = QuranBot()

    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set in environment.")
        return

    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
