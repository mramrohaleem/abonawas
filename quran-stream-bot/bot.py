import os
import asyncio
import subprocess
import discord
from discord.ext import commands
from modules.logger_config import setup_logger

# Bot intents
intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

# Central logger
logger = setup_logger()

# Verify ffmpeg is available
ffmpeg_ver = subprocess.run(
    ["ffmpeg", "-version"], capture_output=True, text=True
).stdout.splitlines()[0]
logger.info(f"ffmpeg version: {ffmpeg_ver}")

class QuranBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Load only the Player cog; `cogs.ui` is imported by Player
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
