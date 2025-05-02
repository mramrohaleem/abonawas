import asyncio
import logging
import os
from collections import deque
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL

intents = discord.Intents.default()
intents.message_content = False
intents.voice_states = True
intents.guilds = True

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise EnvironmentError("DISCORD_TOKEN environment variable not set.")

YDL_OPTIONS = {
    'format': 'bestaudio/best',
    'quiet': True,
    'default_search': 'auto',
    'noplaylist': True,
}
FFMPEG_OPTIONS = {
    'options': '-vn'
}


class Song:
    def __init__(self, url: str, title: str):
        self.url = url
        self.title = title

    def __str__(self):
        return self.title


class GuildAudio:
    def __init__(self):
        self.queue: deque[Song] = deque()
        self.voice_client: Optional[discord.VoiceClient] = None
        self.now_playing: Optional[Song] = None
        self.panel_message: Optional[discord.Message] = None
        self.disconnect_timer: Optional[asyncio.Task] = None
        self.playing_task: Optional[asyncio.Task] = None
        self.view: Optional[discord.ui.View] = None


class AudioController:
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.guilds: dict[int, GuildAudio] = {}

    def get_guild_audio(self, guild_id: int) -> GuildAudio:
        if guild_id not in self.guilds:
            self.guilds[guild_id] = GuildAudio()
        return self.guilds[guild_id]

    async def enqueue(self, interaction: discord.Interaction, url: str):
        guild_audio = self.get_guild_audio(interaction.guild.id)
        try:
            info = await self._extract_info(url)
            formats = info.get("formats")
            audio_url = next((f["url"] for f in formats if f.get("acodec") != "none"), info["url"])
            song = Song(audio_url, info["title"])
            guild_audio.queue.append(song)
            if not guild_audio.voice_client:
                await self._connect_to_voice(interaction)
            if not guild_audio.playing_task:
                guild_audio.playing_task = asyncio.create_task(self._play_loop(interaction.guild.id))
        except Exception as e:
            logging.error("Error enqueueing song", exc_info=e)
            await interaction.followup.send("❌ فشل في تشغيل الرابط. جرّب رابطًا آخر.", ephemeral=True)

    async def _connect_to_voice(self, interaction: discord.Interaction):
        if not interaction.user.voice or not interaction.user.voice.channel:
            raise RuntimeError("User is not in a voice channel.")
        channel = interaction.user.voice.channel
        vc = await channel.connect()
        self.get_guild_audio(interaction.guild.id).voice_client = vc

    async def _extract_info(self, url: str):
        loop = asyncio.get_event_loop()
        with YoutubeDL(YDL_OPTIONS) as ydl:
            return await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

    async def _play_loop(self, guild_id: int):
        guild_audio = self.get_guild_audio(guild_id)
        while guild_audio.queue:
            guild_audio.now_playing = guild_audio.queue.popleft()
            source = discord.FFmpegPCMAudio(guild_audio.now_playing.url, **FFMPEG_OPTIONS)
            guild_audio.voice_client.play(source, after=lambda e: logging.error("Player error: %s", e) if e else None)
            await self._update_panel(guild_id)
            while guild_audio.voice_client.is_playing():
                await asyncio.sleep(1)
            guild_audio.now_playing = None
        await self._update_panel(guild_id)
        guild_audio.playing_task = None
        await self._start_disconnect_timer(guild_id)

    async def _start_disconnect_timer(self, guild_id: int):
        await asyncio.sleep(60)
        guild_audio = self.get_guild_audio(guild_id)
        if guild_audio.voice_client and (len(guild_audio.voice_client.channel.members) == 1):
            await guild_audio.voice_client.disconnect()
            guild_audio.voice_client = None
            await self._update_panel(guild_id)

    async def _update_panel(self, guild_id: int):
        guild_audio = self.get_guild_audio(guild_id)
        if not guild_audio.panel_message:
            return
        view = ControlPanel(self, guild_id)
        guild_audio.view = view
        embed = discord.Embed(title="🎵 Now Playing" if guild_audio.now_playing else "🔇 Idle")
        if guild_audio.now_playing:
            embed.add_field(name="Track", value=guild_audio.now_playing.title, inline=False)
        await guild_audio.panel_message.edit(embed=embed, view=view)

    async def stop(self, guild_id: int):
        guild_audio = self.get_guild_audio(guild_id)
        if guild_audio.voice_client:
            guild_audio.queue.clear()
            guild_audio.voice_client.stop()
            await self._update_panel(guild_id)


class ControlPanel(discord.ui.View):
    def __init__(self, controller: AudioController, guild_id: int):
        super().__init__(timeout=None)
        self.controller = controller
        self.guild_id = guild_id

    @discord.ui.button(label="⏮️", style=discord.ButtonStyle.gray, disabled=True)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

    @discord.ui.button(label="⏸️", style=discord.ButtonStyle.gray)
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_audio = self.controller.get_guild_audio(self.guild_id)
        vc = guild_audio.voice_client
        if vc and vc.is_playing():
            vc.pause()
            button.label = "▶️"
        elif vc and vc.is_paused():
            vc.resume()
            button.label = "⏸️"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label="⏭️", style=discord.ButtonStyle.gray)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_audio = self.controller.get_guild_audio(self.guild_id)
        if guild_audio.voice_client:
            guild_audio.voice_client.stop()
        await interaction.response.defer()

    @discord.ui.button(label="⏹️", style=discord.ButtonStyle.red)
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.controller.stop(self.guild_id)
        await interaction.response.defer()


bot = commands.Bot(command_prefix="!", intents=intents)
controller = AudioController(bot)


@bot.event
async def on_ready():
    logging.info(f"Bot connected as {bot.user}")
    try:
        synced = await bot.tree.sync()
        logging.info(f"Synced {len(synced)} slash commands.")
    except Exception as e:
        logging.error("Failed to sync commands", exc_info=e)


@bot.tree.command(name="play", description="تشغيل رابط يوتيوب")
@app_commands.describe(url="رابط اليوتيوب")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    await controller.enqueue(interaction, url)
    guild_audio = controller.get_guild_audio(interaction.guild.id)
    if not guild_audio.panel_message:
        embed = discord.Embed(title="🔇 Idle")
        view = ControlPanel(controller, interaction.guild.id)
        panel_msg = await interaction.channel.send(embed=embed, view=view)
        guild_audio.panel_message = panel_msg


@bot.tree.command(name="queue", description="عرض قائمة الانتظار الحالية")
async def queue(interaction: discord.Interaction):
    guild_audio = controller.get_guild_audio(interaction.guild.id)
    if not guild_audio.queue:
        await interaction.response.send_message("📭 قائمة الانتظار فارغة.", ephemeral=True)
        return
    embed = discord.Embed(title="🎶 قائمة الانتظار")
    for idx, song in enumerate(guild_audio.queue, 1):
        embed.add_field(name=f"{idx}.", value=song.title, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


bot.run(TOKEN)

