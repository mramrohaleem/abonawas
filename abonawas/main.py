import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import logging
import os
from typing import List, Optional

intents = discord.Intents.default()
intents.message_content = False
bot = commands.Bot(command_prefix="!", intents=intents)

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

FFMPEG_OPTIONS = {
    'before_options': '-nostdin',
    'options': '-vn'
}

COOKIES_PATH = "cookies.txt"

class GuildMusicState:
    def __init__(self):
        self.queue: List[str] = []
        self.voice_client: Optional[discord.VoiceClient] = None
        self.play_next_song = asyncio.Event()
        self.current_task: Optional[asyncio.Task] = None

    async def audio_player_task(self, ctx: discord.Interaction):
        while True:
            self.play_next_song.clear()

            if not self.queue:
                await asyncio.sleep(60)
                if not self.voice_client or not self.voice_client.is_connected():
                    break
                if not self.voice_client.channel.members or len(self.voice_client.channel.members) == 1:
                    await self.voice_client.disconnect()
                    break
                continue

            url = self.queue.pop(0)
            try:
                info = await self._extract_info(url)
                source_url = info['url']
                title = info.get('title', 'Unknown Title')

                logging.info(f"Now playing: {title}")
                audio = discord.FFmpegPCMAudio(source_url, **FFMPEG_OPTIONS)
                self.voice_client.play(audio, after=lambda e: self.play_next_song.set())
                await ctx.followup.send(f"🎶 Now playing: **{title}**", ephemeral=False)
                await self.play_next_song.wait()

            except Exception as e:
                logging.error("Error playing song", exc_info=e)
                await ctx.followup.send("❌ فشل في تشغيل الرابط. جرّب رابطًا آخر", ephemeral=True)

    async def enqueue(self, ctx: discord.Interaction, url: str):
        self.queue.append(url)
        if not self.current_task or self.current_task.done():
            self.current_task = asyncio.create_task(self.audio_player_task(ctx))

    async def _extract_info(self, url: str):
        # دعم روابط invidious و piped
        if "piped." in url or "invidio." in url or "yewtu.be" in url:
            if "v=" in url:
                video_id = url.split("v=")[-1].split("&")[0]
            elif "/watch/" in url:
                video_id = url.split("/watch/")[-1]
            elif "/watch/" not in url:
                video_id = url.split("/")[-1]
            url = f"https://www.youtube.com/watch?v={video_id}"

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'cookiefile': COOKIES_PATH,
        }
        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

music_states = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    logging.info(f"Bot connected as {bot.user}")

@bot.tree.command(name="play", description="تشغيل رابط يوتيوب أو Invidious")
@app_commands.describe(url="رابط الفيديو")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    guild_id = interaction.guild.id
    state = music_states.get(guild_id)
    if state is None:
        state = GuildMusicState()
        music_states[guild_id] = state

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ يجب أن تكون في قناة صوتية أولاً", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel

    if not state.voice_client or not state.voice_client.is_connected():
        state.voice_client = await voice_channel.connect()

    await state.enqueue(interaction, url)

@bot.tree.command(name="queue", description="عرض قائمة التشغيل")
async def queue(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    state = music_states.get(guild_id)

    if not state or not state.queue:
        await interaction.response.send_message("📭 القائمة فارغة.", ephemeral=True)
        return

    description = "\n".join(f"{idx+1}. {url}" for idx, url in enumerate(state.queue))
    embed = discord.Embed(title="🎵 قائمة التشغيل", description=description, color=0x00ff00)
    await interaction.response.send_message(embed=embed)

bot.run(os.getenv("DISCORD_TOKEN"))
