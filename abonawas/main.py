import asyncio
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL
from imageio_ffmpeg import get_ffmpeg_exe

# إعدادات السجل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'extract_flat': 'in_playlist',
    'default_search': 'auto',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}

intents = discord.Intents.default()
intents.message_content = False
intents.guilds = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

class Track:
    def __init__(self, url: str, title: str, requester: discord.Member):
        self.url = url
        self.title = title
        self.requester = requester

class GuildAudio:
    def __init__(self):
        self.queue: list[Track] = []
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current: Optional[Track] = None
        self.message: Optional[discord.Message] = None
        self.view: Optional['PlayerView'] = None
        self.inactive_timer: Optional[asyncio.Task] = None

    def is_playing(self) -> bool:
        return self.voice_client and self.voice_client.is_playing()

guild_audio: dict[int, GuildAudio] = {}

def get_guild_audio(guild_id: int) -> GuildAudio:
    if guild_id not in guild_audio:
        guild_audio[guild_id] = GuildAudio()
    return guild_audio[guild_id]

class PlayerView(discord.ui.View):
    def __init__(self, guild_id: int):
        super().__init__(timeout=None)
        self.guild_id = guild_id
        self.update_buttons()

    def update_buttons(self):
        audio = get_guild_audio(self.guild_id)
        is_playing = audio.is_playing()
        has_next = len(audio.queue) > 0

        self.clear_items()
        self.add_item(PreviousButton(disabled=not has_next))
        self.add_item(PauseResumeButton(disabled=not is_playing))
        self.add_item(NextButton(disabled=not has_next))
        self.add_item(StopButton(disabled=not is_playing))

class PreviousButton(discord.ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(style=discord.ButtonStyle.secondary, emoji='⏮️', disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class PauseResumeButton(discord.ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(style=discord.ButtonStyle.secondary, emoji='⏸️', disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        audio = get_guild_audio(interaction.guild.id)
        vc = audio.voice_client
        if vc.is_paused():
            vc.resume()
        else:
            vc.pause()
        await interaction.response.defer()

class NextButton(discord.ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(style=discord.ButtonStyle.secondary, emoji='⏭️', disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        audio = get_guild_audio(interaction.guild.id)
        if audio.voice_client and audio.is_playing():
            audio.voice_client.stop()
        await interaction.response.defer()

class StopButton(discord.ui.Button):
    def __init__(self, disabled: bool):
        super().__init__(style=discord.ButtonStyle.danger, emoji='⏹️', disabled=disabled)

    async def callback(self, interaction: discord.Interaction):
        audio = get_guild_audio(interaction.guild.id)
        if audio.voice_client:
            await audio.voice_client.disconnect()
            audio.queue.clear()
            audio.current = None
            audio.message = None
        await interaction.response.defer()

async def play_next(guild_id: int):
    audio = get_guild_audio(guild_id)

    if not audio.queue:
        audio.current = None
        if audio.view:
            audio.view.update_buttons()
        await update_control_message(guild_id)
        return

    track = audio.queue.pop(0)
    audio.current = track

    with YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(track.url, download=False)
            if 'url' in info:
                url2 = info['url']
            elif 'entries' in info and info['entries']:
                url2 = info['entries'][0].get('url')
                if not url2:
                    raise KeyError
            else:
                raise KeyError
        except Exception as e:
            logging.error(f"فشل استخراج الصوت: {e}")
            await play_next(guild_id)
            return

    vc = audio.voice_client
    if vc:
        source = discord.FFmpegPCMAudio(url2, executable=get_ffmpeg_exe(), **FFMPEG_OPTIONS)
        vc.play(
            source,
            after=lambda e: bot.loop.call_soon_threadsafe(asyncio.create_task, play_next(guild_id))
        )
        vc.source = source  # ✅ هذا يمنع إنشاء Opus Encoder

    if audio.view:
        audio.view.update_buttons()
    await update_control_message(guild_id)

async def update_control_message(guild_id: int):
    audio = get_guild_audio(guild_id)
    if audio.message:
        desc = f"🎶 الآن يشغل: **{audio.current.title}**" if audio.current else "لا يوجد تشغيل حالياً."
        try:
            await audio.message.edit(content=desc, view=audio.view)
        except Exception as e:
            logging.error(f"فشل تحديث الرسالة: {e}")

@tree.command(name="play", description="شغل رابط تلاوة من SoundCloud")
@app_commands.describe(url="رابط SoundCloud صالح")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("يجب أن تكون في قناة صوتية أولاً.", ephemeral=True)
        return

    audio = get_guild_audio(interaction.guild.id)
    channel = interaction.user.voice.channel

    if not audio.voice_client or not audio.voice_client.is_connected():
        audio.voice_client = await channel.connect()

    with YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception:
            await interaction.followup.send("تعذر استخراج الرابط، تأكد من صحته.", ephemeral=True)
            return

    track = Track(url, info.get('title', 'بدون عنوان'), interaction.user)
    audio.queue.append(track)

    if not audio.view:
        audio.view = PlayerView(interaction.guild.id)

    if not audio.message:
        msg = await interaction.followup.send(content="🎶 جاري التشغيل...", view=audio.view)
        audio.message = msg
    else:
        await update_control_message(interaction.guild.id)

    if not audio.is_playing():
        await play_next(interaction.guild.id)

@tree.command(name="queue", description="عرض قائمة التشغيل")
async def queue(interaction: discord.Interaction):
    audio = get_guild_audio(interaction.guild.id)
    if not audio.queue:
        await interaction.response.send_message("📭 قائمة التشغيل فارغة.")
        return

    desc = ""
    for i, track in enumerate(audio.queue, 1):
        desc += f"{i}. {track.title} (طلبه {track.requester.display_name})\n"

    embed = discord.Embed(title="قائمة التشغيل", description=desc, color=0x00ff00)
    await interaction.response.send_message(embed=embed)

@bot.event
async def on_ready():
    await tree.sync()
    logging.info(f"تم تسجيل الدخول باسم {bot.user}")

@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return

    audio = get_guild_audio(member.guild.id)
    vc = audio.voice_client

    if not vc or not vc.is_connected() or vc.channel != before.channel:
        return

    if len(vc.channel.members) == 1:
        if audio.inactive_timer:
            audio.inactive_timer.cancel()

        async def disconnect_later():
            await asyncio.sleep(60)
            if vc and len(vc.channel.members) == 1:
                await vc.disconnect()
                audio.queue.clear()
                audio.message = None
                audio.current = None

        audio.inactive_timer = asyncio.create_task(disconnect_later())

    elif len(vc.channel.members) > 1 and audio.inactive_timer:
        audio.inactive_timer.cancel()

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logging.error("يرجى تحديد متغير البيئة DISCORD_TOKEN")
    else:
        bot.run(token)
