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
    Cog لتنفيذ أوامر السلاش لبث التلاوات من MP3 أو YouTube.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger()
        self.downloader = Downloader(self.logger)
        self.players: dict[int, dict] = {}

    # ---------------- حالة السيرفر ----------------
    def get_state(self, gid: int) -> dict:
        return self.players.setdefault(gid, {
            "queue": deque(), "vc": None, "current": None,
            "timer_task": None, "download_task": None, "message": None
        })

    # ---------------- أمر stream / yt ----------------
    @app_commands.command(name="stream", description="أضف رابط MP3 أو YouTube للطابور وابدأ التشغيل")
    @app_commands.describe(url="رابط مباشر MP3 أو رابط يوتيوب")
    async def stream(self, interaction: discord.Interaction, url: str):
        await self._handle_stream(interaction, url)

    @app_commands.command(name="yt", description="اختصار لإضافة فيديو يوتيوب")
    @app_commands.describe(url="رابط فيديو YouTube")
    async def yt(self, interaction: discord.Interaction, url: str):
        await self._handle_stream(interaction, url)

    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("🚫 يجب أن تكون في قناة صوتية.", ephemeral=True)

        await interaction.response.defer(thinking=True)  # يرسل ...is thinking
        st = self.get_state(interaction.guild_id)
        st["queue"].append(url)
        self.logger.info(f"[{interaction.guild_id}] أضيف للطابور: {url}")

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()
            self.logger.info(f"[{interaction.guild_id}] تم الاتصال بالصوت")

        if not st["current"]:
            await self._play_next(interaction, is_initial=True)
        else:
            await interaction.followup.send(f"➕ تمت الإضافة للطابور (الموقع {len(st['queue'])})", ephemeral=True)

    # ---------------- أوامر التحكم ----------------
    @app_commands.command(name="play", description="تشغيل أو استئناف المسار الحالي")
    async def play(self, interaction: discord.Interaction):
        st, vc = self.get_state(interaction.guild_id), None
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild_id}] استئناف")
            return await interaction.response.send_message("▶️ تم الاستئناف", ephemeral=True)
        if (not vc or not vc.is_playing()) and st["queue"]:
            await interaction.response.defer(thinking=True)
            await self._play_next(interaction, False)
            return
        await interaction.response.send_message("لا يوجد شيء للتشغيل.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st, vc = self.get_state(interaction.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            self.logger.info(f"[{interaction.guild_id}] إيقاف مؤقت")
            return await interaction.response.send_message("⏸️ تم الإيقاف مؤقتًا", ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يُشغَّل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المسار الحالي")
    async def skip(self, interaction: discord.Interaction):
        st, vc = self.get_state(interaction.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.stop()
            self.logger.info(f"[{interaction.guild_id}] تخطي")
            return await interaction.response.send_message("⏭️ تم التخطي", ephemeral=True)
        await interaction.response.send_message("⏭️ لا شيء يُشغَّل.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف التشغيل ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏹️ تم الإيقاف ومسح الطابور", ephemeral=True)
        st = self.get_state(interaction.guild_id)
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        st["queue"].clear()
        st["current"] = None
        if st["timer_task"]:
            st["timer_task"].cancel()
        self.logger.info(f"[{interaction.guild_id}] إيقاف كامل")

    @app_commands.command(name="help", description="عرض الأوامر")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 أوامر البوت", color=0x2ecc71)
        cmds = {
            "/stream [url]": "أضف رابط MP3 أو YouTube",
            "/yt [url]": "اختصار لإضافة يوتيوب",
            "/play": "تشغيل أو استئناف",
            "/pause": "إيقاف مؤقت",
            "/skip": "تخطي",
            "/stop": "إيقاف ومسح الطابور",
            "/help": "هذه الرسالة"
        }
        for n, d in cmds.items():
            embed.add_field(name=n, value=d, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------------- التشغيل الداخلي ----------------
    async def _play_next(self, interaction: discord.Interaction, is_initial: bool):
        st = self.get_state(interaction.guild_id)
        if st["timer_task"]: st["timer_task"].cancel()
        if not st["queue"]:
            if st["vc"]: await st["vc"].disconnect()
            st["current"] = None
            return

        url = st["queue"].popleft()
        self.logger.info(f"🔗 يتم تنزيل الرابط: {url}")
        path = await self.downloader.download(url)
        self.logger.info(f"✅ تم التنزيل في: {path}")
        st["current"] = path

        if st["queue"]:
            st["download_task"] = asyncio.create_task(self.downloader.download(st["queue"][0]))

        source = discord.FFmpegOpusAudio(
            path, executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn"
        )
        st["vc"].play(source, after=lambda e: self.bot.loop.create_task(self._after_play(interaction, e)))
        self.logger.info(f"[{interaction.guild_id}] بدأ التشغيل: {path}")

        audio = MP3(path); dur = int(audio.info.length)
        embed = discord.Embed(title=path.split('/')[-1], color=0x3498db)
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)
        embed.add_field(name="طول الطابور", value=str(len(st["queue"])), inline=True)

        if is_initial:
            # استبدل رسالة thinking
            await interaction.followup.edit_message(message_id=interaction.original_response().id, content=None, embed=embed)
            st["message"] = await interaction.original_response()
        else:
            await st["message"].edit(embed=embed)

        st["timer_task"] = self.bot.loop.create_task(self._update_timer(interaction.guild_id, dur))

    async def _after_play(self, interaction: discord.Interaction, error):
        if error: self.logger.error(f"Playback error: {error}", exc_info=True)
        await self._play_next(interaction, False)

    async def _update_timer(self, gid: int, total: int):
        st = self.get_state(gid); start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["message"].embeds[0]
            embed.set_field_at(0, name="المدة", value=self._fmt(total), inline=True)
            embed.set_field_at(1, name="المنقضي", value=self._fmt(elapsed), inline=True)
            await st["message"].edit(embed=embed)
            await asyncio.sleep(10)

    @staticmethod
    def _fmt(sec: int) -> str:
        m, s = divmod(sec, 60)
        return f"{m:02}:{s:02}"

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
