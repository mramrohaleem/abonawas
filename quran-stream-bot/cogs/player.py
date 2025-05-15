# cogs/player.py

import discord
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
import asyncio
from collections import deque
from datetime import datetime

class Player(commands.Cog):
    """
    Cog implementing slash commands for audio streaming.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger()
        self.downloader = Downloader(self.logger)
        self.players: dict[int, dict] = {}

    def get_state(self, guild_id: int) -> dict:
        return self.players.setdefault(guild_id, {
            "queue": deque(),
            "vc": None,
            "current": None,
            "timer_task": None,
            "download_task": None,
            "message": None
        })

    @app_commands.command(name="stream", description="Stream an MP3 URL into your voice channel")
    @app_commands.describe(url="Direct URL to an MP3 file")
    async def slash_stream(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "🚫 You must be in a voice channel.", ephemeral=True
            )
        await interaction.response.defer(thinking=True)
        st = self.get_state(interaction.guild_id)
        st["queue"].append(url)
        self.logger.info(f"[{interaction.guild_id}] Queued URL: {url}")

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()
            self.logger.info(f"[{interaction.guild_id}] Connected to voice channel")

        if not st["current"]:
            await self._play_next(interaction, is_initial=True)
        else:
            await interaction.followup.send(
                f"➕ Added to queue. Position: {len(st['queue'])}", ephemeral=True
            )

    @app_commands.command(name="play", description="Play or resume the current track")
    async def slash_play(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        # If paused, resume
        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild_id}] Resumed via /play")
            return await interaction.response.send_message("▶️ Resumed playback", ephemeral=True)
        # If nothing playing but queue exists, start next
        if not vc or not vc.is_playing():
            if st["queue"]:
                await interaction.response.defer(thinking=True)
                await self._play_next(interaction, is_initial=False)
                return
        # Otherwise nothing to do
        await interaction.response.send_message(
            "Nothing is paused or in the queue to play.", ephemeral=True
        )

    @app_commands.command(name="pause", description="Pause the current track")
    async def slash_pause(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                "⏸️ Nothing is playing.", ephemeral=True
            )
        vc.pause()
        self.logger.info(f"[{interaction.guild_id}] Paused via /pause")
        await interaction.response.send_message("⏸️ Paused playback", ephemeral=True)

    @app_commands.command(name="skip", description="Skip to the next track")
    async def slash_skip(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                "⏭️ Nothing is playing.", ephemeral=True
            )
        vc.stop()
        self.logger.info(f"[{interaction.guild_id}] Skipped via /skip")
        await interaction.response.send_message("⏭️ Skipped to next", ephemeral=True)

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def slash_stop(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if vc:
            vc.stop()
            await vc.disconnect()
        st["queue"].clear()
        st["current"] = None
        if st["timer_task"]:
            st["timer_task"].cancel()
        self.logger.info(f"[{interaction.guild_id}] Stopped via /stop")
        await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)

    @app_commands.command(name="help", description="Show help for all commands")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Quran Stream Bot — Help", color=discord.Color.green())
        cmds = {
            "/stream [url]": "Stream a direct MP3 URL into your voice channel",
            "/play": "Play or resume the current track",
            "/pause": "Pause the current track",
            "/skip": "Skip to the next track",
            "/stop": "Stop playback and clear the queue",
            "/help": "Show this help message"
        }
        for name, desc in cmds.items():
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # Internal playback logic omitted for brevity...
    # Include your _play_next, _after_play, _update_timer, _format_time here

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
