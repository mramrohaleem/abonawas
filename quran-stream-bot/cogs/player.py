import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, Embed
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from cogs.ui import PlayerControls
from mutagen.mp3 import MP3
import asyncio
from collections import deque
from datetime import datetime

class Player(commands.Cog):
    """
    Cog managing the playback queue, voice client, and UI updates.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger()
        self.downloader = Downloader(self.logger)
        # per-guild playback state
        self.players: dict[int, dict] = {}

    def get_state(self, guild_id: int) -> dict:
        """Ensure a state dict exists for guild."""
        state = self.players.setdefault(guild_id, {
            "queue": deque(),
            "vc": None,
            "current": None,
            "embed_msg": None,
            "timer_task": None,
            "download_task": None,
            "controls": PlayerControls(self)
        })
        return state

    @commands.command(name="stream")
    async def stream(self, ctx: commands.Context, url: str):
        """
        Add a direct MP3 URL to the queue and start playback.
        """
        if not ctx.author.voice or not ctx.author.voice.channel:
            return await ctx.send("You must be in a voice channel.")

        st = self.get_state(ctx.guild.id)
        st["queue"].append(url)
        self.logger.info(f"[{ctx.guild.id}] Queued URL: {url}")

        # connect if needed
        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await ctx.author.voice.channel.connect()
            self.logger.info(f"[{ctx.guild.id}] Connected to voice channel.")

        # if nothing playing, start
        if not st["current"]:
            await self._play_next(ctx)
        else:
            await ctx.send(f"Added to queue. Length: {len(st['queue'])}")

    async def _play_next(self, ctx: commands.Context):
        st = self.get_state(ctx.guild.id)

        # cancel any previous timer
        if st["timer_task"]:
            st["timer_task"].cancel()

        # if queue empty, clean up
        if not st["queue"]:
            await self._cleanup(ctx.guild.id)
            return

        url = st["queue"].popleft()
        path = await self.downloader.download(url)
        st["current"] = path

        # pre-download next
        if st["queue"]:
            nxt = st["queue"][0]
            st["download_task"] = asyncio.create_task(self.downloader.download(nxt))

        # prepare audio source with explicit ffmpeg options
        source = FFmpegPCMAudio(
            path,
            executable=self.bot.ffmpeg_exe,
            before_options="-nostdin",
            options="-vn"
        )

        # try to start playback and log any errors
        try:
            st["vc"].play(
                source,
                after=lambda e: self.bot.loop.create_task(self._after_play(ctx, e))
            )
            self.logger.info(f"[{ctx.guild.id}] Started playback of {path}")
        except Exception as e:
            self.logger.error(
                f"[{ctx.guild.id}] Failed to start playback: {e}",
                exc_info=True
            )

        # build embed
        audio = MP3(path)
        dur = int(audio.info.length)
        embed = Embed(
            title=path.split("/")[-1],
            description="Now playing",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Duration", value=self._format_time(dur), inline=True)
        embed.add_field(name="Elapsed", value="00:00", inline=True)
        embed.add_field(name="Queue Length", value=str(len(st["queue"])), inline=True)

        msg = await ctx.send(embed=embed, view=st["controls"])
        st["embed_msg"] = msg

        # start elapsed timer
        st["timer_task"] = self.bot.loop.create_task(self._update_timer(ctx.guild.id, dur))

    async def _after_play(self, ctx: commands.Context, error):
        if error:
            self.logger.error(f"Playback error: {error}", exc_info=True)
        await self._play_next(ctx)

    async def _update_timer(self, guild_id: int, total: int):
        """
        Every 10s, update the embed's elapsed field.
        """
        st = self.get_state(guild_id)
        start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["embed_msg"].embeds[0]
            embed.set_field_at(1, name="Elapsed", value=self._format_time(elapsed), inline=True)
            await st["embed_msg"].edit(embed=embed)
            await asyncio.sleep(10)

    async def resume(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild.id)
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild.id}] Resumed playback")
        await interaction.response.defer()

    async def pause(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild.id)
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            self.logger.info(f"[{interaction.guild.id}] Paused playback")
        await interaction.response.defer()

    async def skip(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild.id)
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.stop()
            self.logger.info(f"[{interaction.guild.id}] Skipped track")
        await interaction.response.defer()

    async def stop(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild.id)
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        st["queue"].clear()
        st["current"] = None
        if st["timer_task"]:
            st["timer_task"].cancel()
        self.logger.info(f"[{interaction.guild.id}] Stopped and cleared queue")
        await interaction.response.defer()

    async def _cleanup(self, guild_id: int):
        st = self.get_state(guild_id)
        if st["vc"]:
            await st["vc"].disconnect()
        st["current"] = None
        if st["timer_task"]:
            st["timer_task"].cancel()
        self.logger.info(f"[{guild_id}] Queue empty, disconnected")

    @staticmethod
    def _format_time(seconds: int) -> str:
        m, s = divmod(seconds, 60)
        return f"{m:02d}:{s:02d}"

# Extension entrypoint for discord.py 2.x
async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
