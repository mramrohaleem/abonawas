# bot.py

import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe
from cogs.player import Player
from cogs.search import Search

logger = setup_logger()

ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # إضافة Cogs
        await self.add_cog(Player(self))
        await self.add_cog(Search(self))

        # مزامنة أوامر السلاش
        await self.tree.sync()
        logger.info("✅ Synced slash commands")

        # تأكيد التحميل في الـ logs
        logger.info(f"Loaded Cogs: {list(self.cogs.keys())}")
        logger.info(f"Slash Commands: {[cmd.name for cmd in self.tree.walk_commands()]}")

    async def on_ready(self):
        logger.info(f"🟢 Logged in as {self.user} (ID: {self.user.id})")

async def main():
    bot = QuranBot()
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("❌ DISCORD_TOKEN not set.")
        return

    await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
