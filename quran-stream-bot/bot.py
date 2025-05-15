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

# Central logger
logger = setup_logger()

# Locate the embedded ffmpeg binary
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)
        # make ffmpeg path available to cogs
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # Load only the Player cog; PlayerControls comes along
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
