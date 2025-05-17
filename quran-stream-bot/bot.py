# bot.py  –  نقطة تشغيل البوت بعد إزالة Cog البحث المنفصل

import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe
from cogs.player import Player   # لم يَعُد هناك Search cog

logger = setup_logger()

ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True            # مطلوب لقنوات الصوت
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # تحميل الـPlayer Cog الوحيد
        await self.add_cog(Player(self))

        # مزامنة أوامر الـSlash مع التطبيق
        await self.tree.sync()
        logger.info("✅ Synced slash commands")

        # طباعة للتأكد من التحميل
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
