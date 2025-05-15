import os
import asyncio
import discord
from discord.ext import commands
from modules.logger_config import setup_logger
from imageio_ffmpeg import get_ffmpeg_exe

logger = setup_logger()

# FFmpeg binary for audio encoding
ffmpeg_exe = get_ffmpeg_exe()
logger.info(f"Using ffmpeg executable at: {ffmpeg_exe}")

class QuranBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.ffmpeg_exe = ffmpeg_exe

    async def setup_hook(self):
        # Load the Player cog (which registers slash commands)
        await self.add_cog(Player(self))
        # Sync slash commands with Discord
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
