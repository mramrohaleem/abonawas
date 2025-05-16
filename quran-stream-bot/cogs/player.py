import discord, asyncio
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from pathlib import Path
from collections import deque
from datetime import datetime

class Player(commands.Cog):
    """تشغيل التلاوات، قوائم التشغيل، إدارة الطابور، وتنزيل مسبق."""
    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger()
        self.dl      = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    # ---------- أدوات حالة ----------
    def _st(self, gid: int):
        return self.states.setdefault(gid, {
            "queue": deque(),   # عناصر في الانتظار (URLs أو مسارات)
            "vc": None,         # VoiceClient
            "current": None,    # المسار الجاري
            "timer": None,      # مهمة تحديث الوقت
            "download_task": None,
            "msg": None         # رسالة الـ Embed
        })

    def _fmt(self, sec: int): m, s = divmod(sec, 60); return f"{m:02}:{s:02}"

    # ---------- أوامر الطابور ----------
    @app_commands.command(name="queue", description="عرض محتويات طابور التشغيل")
    async def queue(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        if not st["queue"] and not st["current"]:
            return await i.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x3498db)
        if st["current"]:
            embed.add_field(name="▶️ الجاري", value=Path(st["current"]).name, inline=False)

        for idx, item in enumerate(list(st["queue"])[:20], 1):
            title = item if isinstance(item, str) and not item.startswith("http") else item.split("/")[-1]
            embed.add_field(name=f"{idx}.", value=title, inline=False)

        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال مباشرةً إلى عنصر داخل الطابور")
    @app_commands.describe(index="رقم العنصر كما يظهر في /queue (يبدأ من 1)")
    async def jump(self, i: discord.Interaction, index: int):
        st = self._st(i.guild_id)
        if index < 1 or index > len(st["queue"]):
            return await i.response.send_message("❌ رقم غير صالح.", ephemeral=True)

        for _ in range(index - 1):
            st["queue"].append(st["queue"].popleft())
        if st["vc"]: st["vc"].stop()
        await i.response.send_message(f"⏩ تم الانتقال إلى العنصر {index}.", ephemeral=True)

    # ---------- أمر stream (فيه دعم Playlist) ----------
    @app_commands.command(name="stream", description="أضف رابط MP3 أو فيديو/قائمة تشغيل YouTube")
    @app_commands.describe(url="الرابط المطلوب")
    async def stream(self, i: discord.Interaction, url: str):
        if not i.user.voice or not i.user.voice.channel:
            return await i.response.send_message("🚫 يلزم الانضمام لقناة صوتية.", ephemeral=True)
        await i.response.defer(thinking=True)

        st = self._st(i.guild_id)
        result = await self.dl.download(url)

        # قائمة تشغيل ← قائمة URLs
        if isinstance(result, list):
            st["queue"].extend(result)
            await i.followup.send(f"📜 أُضيف {len(result)} مقطعاً من قائمة التشغيل.", ephemeral=True)
        else:
            st["queue"].append(result)  # MP3 مفرد أو فيديو تم تحويله
            await i.followup.send("✅ أضيف إلى الطابور.", ephemeral=True)

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await i.user.voice.channel.connect()
        if not st["current"]:
            await self._play_next(i, first=True)

    # ---------- أوامر التحكم الأساسية (play/pause/skip/stop) ----------
    @app_commands.command(name="play", description="تشغيل أو استئناف الإيقاف المؤقت")
    async def play(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            return await i.response.send_message("▶️ تم الاستئناف.", ephemeral=True)
        if (not vc or not vc.is_playing()) and st["queue"]:
            await i.response.defer(thinking=True)
            await self._play_next(i)
            return
        await i.response.send_message("لا يوجد ما يتم تشغيله.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت للتشغيل")
    async def pause(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            return await i.response.send_message("⏸️ تم الإيقاف مؤقتًا.", ephemeral=True)
        await i.response.send_message("⏸️ لا شيء يُشغّل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المقطع الحالي")
    async def skip(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.stop()
            return await i.response.send_message("⏭️ تم التخطي.", ephemeral=True)
        await i.response.send_message("⏭️ لا شيء يُشغّل.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف التشغيل ومسح الطابور")
    async def stop(self, i: discord.Interaction):
        await i.response.send_message("⏹️ تم الإيقاف ومسح الطابور.", ephemeral=True)
        st = self._st(i.guild_id)
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        st["queue"].clear()
        if st["timer"]: st["timer"].cancel()
        st.update(current=None, msg=None)

    # ---------- التشغيل وتسلسل التنزيل المسبق ----------
    async def _play_next(self, i: discord.Interaction, first=False):
        st = self._st(i.guild_id)
        if st["timer"]: st["timer"].cancel()
        if not st["queue"]:
            if st["vc"]: await st["vc"].disconnect()
            st.update(current=None)
            return

        item = st["queue"].popleft()
        # إذا ما زال رابط فيديو → نزّله الآن
        if item.startswith("http"):
            item = await self.dl.download(item)

        st["current"] = item
        # تنزيل العنصر التالي مسبقًا
        if st["queue"]:
            nxt = st["queue"][0]
            if nxt.startswith("http"):
                st["download_task"] = asyncio.create_task(self.dl.download(nxt))

        # التشغيل
        src = discord.FFmpegOpusAudio(item, executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin", options="-vn")
        st["vc"].play(src, after=lambda e: self.bot.loop.create_task(self._after(i, e)))

        audio = MP3(item)
        dur   = int(audio.info.length)
        embed = discord.Embed(title=Path(item).name, color=0x2ecc71)
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)
        embed.add_field(name="المتبقي بالطابور", value=str(len(st["queue"])), inline=True)

        if first:
            st["msg"] = await i.followup.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        st["timer"] = self.bot.loop.create_task(self._ticker(i.guild_id, dur))

    async def _after(self, i: discord.Interaction, err):
        if err: self.logger.error(f"خطأ تشغيل: {err}", exc_info=True)
        await self._play_next(i)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["msg"].embeds[0]
            embed.set_field_at(1, name="المنقضي", value=self._fmt(elapsed), inline=True)
            await st["msg"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
