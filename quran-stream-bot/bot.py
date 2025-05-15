import os
import discord
from discord.ext import commands
from modules.logger_config import setup_logger

intents = discord.Intents.default()
intents.voice_states = True
intents.message_content = True

logger = setup_logger()

def main():
    bot = commands.Bot(command_prefix="!", intents=intents)
    # load cogs
    bot.load_extension("cogs.player")
    bot.load_extension("cogs.ui")  # ensures persistent View

    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN not set in environment.")
        exit(1)

    bot.run(token)

if __name__ == "__main__":
    main()
