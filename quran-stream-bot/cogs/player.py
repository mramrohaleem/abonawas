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
        })

    @app_commands.command(name="stream", description="Stream an MP3 URL into your voice channel")
    @app_commands.describe(url="Direct URL to an MP3 file")
    async def slash_stream(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message(
                "🚫 You must be in a voice channel to use this command.",
                ephemeral=True
            )
        await interaction.response.defer(thinking=True)
        guild_id = interaction.guild_id
        st = self.get_state(guild_id)
        st["queue"].append(url)
        self.logger.info(f"[{guild_id}] Queued URL: {url}")

        # connect if needed
        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()
            self.logger.info(f"[{guild_id}] Connected to voice channel")

        # if nothing playing, kick off playback
        if not st["current"]:
            await self._play_next(interaction, is_initial=True)
            return  # the reply done inside _play_next
        else:
            return await interaction.followup.send(
                f"➕ Added to queue. Position: {len(st['queue'])}",
                ephemeral=True
            )

    async def _play_next(self, interaction: discord.Interaction, is_initial=False):
        guild_id = interaction.guild_id
        st = self.get_state(guild_id)

        # cancel previous timer
        if st["timer_task"]:
            st["timer_task"].cancel()

        if not st["queue"]:
            # nothing left
            await st["vc"].disconnect()
            st["current"] = None
            return

        url = st["queue"].popleft()
        local_path = await self.downloader.download(url)
        st["current"] = local_path

        # prefetch next
        if st["queue"]:
            st["download_task"] = asyncio.create_task(
                self.downloader.download(st["queue"][0])
            )

        # play via FFmpegOpusAudio
        source = discord.FFmpegOpusAudio(
            local_path,
            executable=self.bot.ffmpeg_exe,
            before_options="-nostdin",
            options="-vn"
        )
        st["vc"].play(
            source,
            after=lambda e: self.bot.loop.create_task(self._after_play(interaction, e))
        )
        self.logger.info(f"[{guild_id}] Started playback: {local_path}")

        # build embed
        audio = MP3(local_path)
        duration = int(audio.info.length)
        embed = discord.Embed(
            title=local_path.split("/")[-1],
            color=discord.Color.blurple()
        )
        embed.add_field(name="Duration", value=self._format_time(duration), inline=True)
        embed.add_field(name="Queue Length", value=str(len(st["queue"])), inline=True)

        if is_initial:
            # initial reply
            st["message"] = await interaction.followup.send(embed=embed)
        else:
            # update existing
            await st["message"].edit(embed=embed)

        # start elapsed timer
        st["timer_task"] = self.bot.loop.create_task(
            self._update_timer(guild_id, duration)
        )

    async def _after_play(self, interaction: discord.Interaction, error):
        if error:
            self.logger.error(f"Playback error: {error}", exc_info=True)
        # continue to next track
        await self._play_next(interaction)

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

    @app_commands.command(name="pause", description="Pause the current track")
    async def slash_pause(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                "⏸️ Nothing is playing.", ephemeral=True
            )
        vc.pause()
        self.logger.info(f"[{interaction.guild_id}] Paused playback")
        await interaction.response.send_message("⏸️ Paused", ephemeral=True)

    @app_commands.command(name="resume", description="Resume playback")
    async def slash_resume(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_paused():
            return await interaction.response.send_message(
                "▶️ Nothing to resume.", ephemeral=True
            )
        vc.resume()
        self.logger.info(f"[{interaction.guild_id}] Resumed playback")
        await interaction.response.send_message("▶️ Resumed", ephemeral=True)

    @app_commands.command(name="skip", description="Skip to the next track")
    async def slash_skip(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]
        if not vc or not vc.is_playing():
            return await interaction.response.send_message(
                "⏭️ Nothing is playing.", ephemeral=True
            )
        vc.stop()
        self.logger.info(f"[{interaction.guild_id}] Skipped track")
        await interaction.response.send_message("⏭️ Skipped", ephemeral=True)

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
        self.logger.info(f"[{interaction.guild_id}] Stopped playback and cleared queue")
        await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)

    @app_commands.command(name="help", description="Show help for all commands")
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Quran Stream Bot — Help",
            color=discord.Color.green()
        )
        cmds = {
            "/stream [url]": "Stream a direct MP3 URL into your voice channel",
            "/pause": "Pause the current track",
            "/resume": "Resume paused playback",
            "/skip": "Skip to the next track",
            "/stop": "Stop playback and clear the queue",
            "/help": "Show this help message"
        }
        for name, desc in cmds.items():
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    def _format_time(sec: int) -> str:
        m, s = divmod(sec, 60)
        return f"{m:02d}:{s:02d}"

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
