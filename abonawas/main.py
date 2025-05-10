import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import yt_dlp
import logging
import os

intents = discord.Intents.default()
intents.message_content = False
intents.voice_states = True
intents.guilds = True

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

bot = commands.Bot(command_prefix="!", intents=intents)

class GuildAudioState:
    def __init__(self):
        self.queue = asyncio.Queue()
        self.play_next_song = asyncio.Event()
        self.voice_client = None
        self.current = None

    async def audio_player_task(self):
        while True:
            self.play_next_song.clear()
            self.current = await self.queue.get()
            url = self.current

            try:
                info = await self._extract_info(url)
                source = await self._create_source(info)
                self.voice_client.play(source, after=lambda _: asyncio.run_coroutine_threadsafe(self.toggle_next(), bot.loop))
            except Exception as e:
                logging.error("Error playing song", exc_info=e)
                await self.toggle_next()
                continue

            await self.play_next_song.wait()

    async def toggle_next(self):
        self.play_next_song.set()

    async def enqueue(self, url: str):
        await self.queue.put(url)

    async def _extract_info(self, url: str):
        # نحظر روابط يوتيوب فقط
        if "youtube.com" in url or "youtu.be" in url:
            raise ValueError("❌ يوتيوب غير مدعوم حاليًا. جرّب رابطًا من SoundCloud أو Vimeo أو موقع آخر.")

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'extract_flat': False,
            'source_address': '0.0.0.0',
        }

        loop = asyncio.get_event_loop()
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

    async def _create_source(self, info):
        return discord.FFmpegPCMAudio(info['url'], before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5")


guild_states = {}

@bot.event
async def on_ready():
    await bot.tree.sync()
    logging.info(f"Bot connected as {bot.user}")

@bot.tree.command(name="play", description="تشغيل رابط صوتي من SoundCloud أو موقع صوتي آخر")
@app_commands.describe(url="الرابط الصوتي")
async def play(interaction: discord.Interaction, url: str):
    await interaction.response.defer()

    guild_id = interaction.guild.id
    if guild_id not in guild_states:
        guild_states[guild_id] = GuildAudioState()

    state = guild_states[guild_id]

    if interaction.user.voice is None or interaction.user.voice.channel is None:
        await interaction.followup.send("❌ يجب أن تكون في قناة صوتية أولاً.")
        return

    voice_channel = interaction.user.voice.channel

    if state.voice_client is None or not state.voice_client.is_connected():
        state.voice_client = await voice_channel.connect()
        bot.loop.create_task(state.audio_player_task())

    try:
        await state.enqueue(url)
        await interaction.followup.send(f"✅ تم إضافة الرابط إلى قائمة الانتظار:
{url}")
    except ValueError as e:
        await interaction.followup.send(str(e))
    except Exception:
        logging.exception("Error enqueueing song")
        await interaction.followup.send("❌ فشل في تشغيل الرابط. تأكد أنه رابط من موقع صوتي مدعوم.")

@bot.tree.command(name="skip", description="تخطي المقطع الحالي")
async def skip(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_states and guild_states[guild_id].voice_client:
        guild_states[guild_id].voice_client.stop()
        await interaction.response.send_message("⏭️ تم التخطي.")
    else:
        await interaction.response.send_message("❌ لا يوجد شيء يتم تشغيله حالياً.")

@bot.tree.command(name="stop", description="إيقاف التشغيل والمغادرة")
async def stop(interaction: discord.Interaction):
    guild_id = interaction.guild.id
    if guild_id in guild_states and guild_states[guild_id].voice_client:
        await guild_states[guild_id].voice_client.disconnect()
        guild_states[guild_id].voice_client = None
        await interaction.response.send_message("⏹️ تم الإيقاف والمغادرة.")
    else:
        await interaction.response.send_message("❌ البوت غير متصل حالياً.")

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    logging.error("DISCORD_TOKEN environment variable not set.")
else:
    bot.run(TOKEN)

