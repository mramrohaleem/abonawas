# bot.py

import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe
from cogs.player import Player

logger = setup_logger()

# مسار FFmpeg المضمّن لترميز Opus
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # تحميل Cog الخاص بالتشغيل
        await self.add_cog(Player(self))
        # مزامنة أوامر السلاش مع Discord
        await self.tree.sync()
        logger.info("Synced slash commands")

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
