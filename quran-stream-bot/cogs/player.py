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
        # per-guild playback state
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

    @app_commands.command(
        name="stream",
        description="Stream an MP3 URL into your voice channel"
    )
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
                f"➕ Added to queue. Position: {len(st['queue'])}",
                ephemeral=True
            )

    @app_commands.command(
        name="play",
        description="Play or resume the current track"
    )
    async def slash_play(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]

        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild_id}] Resumed via /play")
            return await interaction.response.send_message(
                "▶️ Resumed playback", ephemeral=True
            )

        if (not vc or not vc.is_playing()) and st["queue"]:
            await interaction.response.defer(thinking=True)
            await self._play_next(interaction, is_initial=False)
            return

        await interaction.response.send_message(
            "Nothing is paused or in the queue to play.", ephemeral=True
        )

    @app_commands.command(
        name="pause",
        description="Pause the current track"
    )
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

    @app_commands.command(
        name="skip",
        description="Skip to the next track"
    )
    async def slash_skip(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                "⏭️ Nothing is playing.", ephemeral=True
            )
        vc.stop()
        self.logger.info(f"[{interaction.guild_id}] Skipped via /skip")
        await interaction.response.send_message("⏭️ Skipped track", ephemeral=True)

    @app_commands.command(
        name="stop",
        description="Stop playback and clear the queue"
    )
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
        await interaction.response.send_message(
            "⏹️ Stopped playback and cleared queue", ephemeral=True
        )

    @app_commands.command(
        name="help",
        description="Show help for all commands"
    )
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Quran Stream Bot — Help",
            color=discord.Color.green()
        )
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

    async def _play_next(self, interaction: discord.Interaction, is_initial: bool):
        st = self.get_state(interaction.guild_id)

        if st["timer_task"]:
            st["timer_task"].cancel()

        if not st["queue"]:
            if st["vc"]:
                await st["vc"].disconnect()
            st["current"] = None
            return

        url = st["queue"].popleft()
        path = await self.downloader.download(url)
        st["current"] = path

        if st["queue"]:
            st["download_task"] = asyncio.create_task(
                self.downloader.download(st["queue"][0])
            )

        source = discord.FFmpegOpusAudio(
            path,
            executable=self.bot.ffmpeg_exe,
            before_options="-nostdin",
            options="-vn"
        )
        st["vc"].play(
            source,
            after=lambda e: self.bot.loop.create_task(self._after_play(interaction, e))
        )
        self.logger.info(f"[{interaction.guild_id}] Started playback: {path}")

        audio = MP3(path)
        dur = int(audio.info.length)
        embed = discord.Embed(
            title=path.split("/")[-1],
            color=discord.Color.blurple()
        )
        embed.add_field(name="Duration", value=self._format_time(dur), inline=True)
        embed.add_field(name="Queue Length", value=str(len(st["queue"])), inline=True)

        if is_initial:
            st["message"] = await interaction.followup.send(embed=embed)
        else:
            await st["message"].edit(embed=embed)

        st["timer_task"] = self.bot.loop.create_task(self._update_timer(interaction.guild_id, dur))

    async def _after_play(self, interaction: discord.Interaction, error):
        if error:
            self.logger.error(f"Playback error: {error}", exc_info=True)
        await self._play_next(interaction, is_initial=False)

    async def _update_timer(self, guild_id: int, total: int):
        st = self.get_state(guild_id)
        start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["message"].embeds[0]
            embed.set_field_at(0, name="Duration", value=self._format_time(total), inline=True)
            embed.set_field_at(1, name="Elapsed", value=self._format_time(elapsed), inline=True)
            await st["message"].edit(embed=embed)
            await asyncio.sleep(10)

    @staticmethod
    def _format_time(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
