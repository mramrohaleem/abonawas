import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe
import discord.opus

# إعداد الصلاحيات التي يحتاجها البوت
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

# تهيئة الـ logger المركزي
logger = setup_logger()

# تحديد مسار ffmpeg المضمّن
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

# محاولة تحميل مكتبة Opus C
try:
    discord.opus.load_opus("libopus.so.0")
    logger.info("Successfully loaded libopus.so.0")
except Exception as e:
    logger.error(f"Could not load Opus library: {e}", exc_info=True)

class QuranBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # حفظ مسار ffmpeg لتمريره للـ Cog
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # تحميل الـ Player cog فقط
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
