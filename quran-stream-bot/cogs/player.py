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
    بثّ تلاوات من روابط MP3 أو YouTube عبر أوامر سلاش بالكامل بالعربية.
    """
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger()
        self.loader  = Downloader(self.logger)
        self.states: dict[int, dict] = {}   # حالة كل سيرفر

    # ---------- أدوات داخليّة ----------
    def _state(self, gid: int) -> dict:
        return self.states.setdefault(gid, {
            "queue": deque(), "vc": None, "current": None,
            "timer_task": None, "download_task": None, "message": None
        })

    def _fmt(self, sec: int) -> str:
        m, s = divmod(sec, 60)
        return f"{m:02}:{s:02}"

    # ---------- أوامر سلاش ----------
    @app_commands.command(name="stream", description="أضف رابط MP3 أو YouTube للطابور وابدأ التشغيل")
    @app_commands.describe(url="رابط مباشر MP3 أو فيديو YouTube/ساوندكلاود")
    async def stream(self, interaction: discord.Interaction, url: str):
        await self._enqueue_and_play(interaction, url)

    @app_commands.command(name="yt", description="اختصار لإضافة رابط YouTube")
    @app_commands.describe(url="رابط YouTube")
    async def yt(self, interaction: discord.Interaction, url: str):
        await self._enqueue_and_play(interaction, url)

    @app_commands.command(name="play", description="تشغيل أو استئناف ما هو متوقف")
    async def play(self, interaction: discord.Interaction):
        st = self._state(interaction.guild_id)
        vc = st["vc"]

        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild_id}] استئناف")
            return await interaction.response.send_message("▶️ تم الاستئناف", ephemeral=True)

        if (not vc or not vc.is_playing()) and st["queue"]:
            await interaction.response.defer(thinking=True)
            await self._play_next(interaction, False)
            return

        await interaction.response.send_message("لا يوجد شيء لتشغيله.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st, vc = self._state(interaction.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            self.logger.info(f"[{interaction.guild_id}] إيقاف مؤقت")
            return await interaction.response.send_message("⏸️ تم الإيقاف مؤقتًا", ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يُشغّل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المسار الحالي")
    async def skip(self, interaction: discord.Interaction):
        st, vc = self._state(interaction.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.stop()
            self.logger.info(f"[{interaction.guild_id}] تخطي")
            return await interaction.response.send_message("⏭️ تم التخطي", ephemeral=True)
        await interaction.response.send_message("⏭️ لا شيء يُشغّل.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف التشغيل ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏹️ تم الإيقاف ومسح الطابور", ephemeral=True)
        st = self._state(interaction.guild_id)
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        st["queue"].clear()
        if st["timer_task"]: st["timer_task"].cancel()
        st.update(current=None, message=None)
        self.logger.info(f"[{interaction.guild_id}] تم الإيقاف الكامل")

    @app_commands.command(name="help", description="عرض قائمة الأوامر")
    async def helper(self, interaction: discord.Interaction):
        embed = discord.Embed(title="📖 أوامر أبو نواس", color=0x2ecc71)
        for cmd, desc in {
            "/stream [رابط]": "أضف رابط MP3 أو YouTube للطابور",
            "/yt [رابط]":    "اختصار لإضافة يوتيوب",
            "/play":         "تشغيل أو استئناف",
            "/pause":        "إيقاف مؤقت",
            "/skip":         "تخطي",
            "/stop":         "إيقاف ومسح الطابور",
            "/help":         "عرض هذه الرسالة"
        }.items():
            embed.add_field(name=cmd, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ---------- تنفيذ الطابور ----------
    async def _enqueue_and_play(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("🚫 يجب أن تكون في قناة صوتية.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        st = self._state(interaction.guild_id)
        st["queue"].append(url)
        self.logger.info(f"[{interaction.guild_id}] في الطابور: {url}")

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()
            self.logger.info(f"[{interaction.guild_id}] متصل بالصوت")

        if not st["current"]:
            await self._play_next(interaction, True)
        else:
            await interaction.followup.send(f"➕ أُضيف للطابور (الموقع {len(st['queue'])})", ephemeral=True)

    async def _play_next(self, interaction: discord.Interaction, first: bool):
        st = self._state(interaction.guild_id)
        if st["timer_task"]: st["timer_task"].cancel()

        if not st["queue"]:
            if st["vc"]: await st["vc"].disconnect()
            st.update(current=None)
            return

        url = st["queue"].popleft()
        self.logger.info(f"🔗 تنزيل: {url}")
        try:
            path = await self.loader.download(url)
        except RuntimeError as err:
            await interaction.followup.send(f"⚠️ {err}", ephemeral=True)
            return

        st["current"] = path
        if st["queue"]:
            st["download_task"] = asyncio.create_task(self.loader.download(st["queue"][0]))

        src = discord.FFmpegOpusAudio(path, executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin", options="-vn")
        st["vc"].play(src, after=lambda e: self.bot.loop.create_task(self._after(interaction, e)))
        self.logger.info(f"[{interaction.guild_id}] تشغيل: {path}")

        # --- Embed معلومات ---
        audio = MP3(path); dur = int(audio.info.length)
        embed = discord.Embed(title=Path(path).name, color=0x3498db)
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)
        embed.add_field(name="طول الطابور", value=str(len(st["queue"])), inline=True)

        if first:
            await interaction.followup.edit_message(message_id=interaction.original_response().id, content=None, embed=embed)
            st["message"] = await interaction.original_response()
        else:
            await st["message"].edit(embed=embed)

        st["timer_task"] = self.bot.loop.create_task(self._ticker(interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err: self.logger.error(f"Playback error: {err}", exc_info=True)
        await self._play_next(interaction, False)

    async def _ticker(self, gid: int, total: int):
        st = self._state(gid)
        started = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - started).total_seconds())
            embed = st["message"].embeds[0]
            embed.set_field_at(0, name="المدة", value=self._fmt(total), inline=True)
            embed.set_field_at(1, name="المنقضي", value=self._fmt(elapsed), inline=True)
            await st["message"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
