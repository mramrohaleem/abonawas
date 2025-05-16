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
    """تشغيل تلاوات، قوائم تشغيل، إدارة طابور مع عناوين وفهرسة."""
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger()
        self.dl     = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    # ---------- حالة السيرفر ----------
    def _st(self, gid: int):
        return self.states.setdefault(gid, {
            "queue": deque(),   # deque[dict]
            "index": 0,         # رقم العنصر الجاري (يبدأ 1)
            "vc": None,
            "current": None,    # dict {"path"/"url","title"}
            "timer": None,
            "download_task": None,
            "msg": None
        })

    def _fmt(self, s: int): m, s = divmod(s, 60); return f"{m:02}:{s:02}"

    # ---------- أوامر الطابور ----------
    @app_commands.command(name="queue", description="عرض طابور التشغيل")
    async def queue(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        if not st["queue"] and not st["current"]:
            return await i.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x3498db)
        if st["current"]:
            embed.add_field(name=f"▶️ {st['index']}.", value=st["current"]["title"], inline=False)

        for offs, elem in enumerate(list(st["queue"])[:20], 1):
            embed.add_field(name=f"{st['index']+offs}.", value=elem["title"], inline=False)

        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="التخطي إلى عنصر محدد")
    @app_commands.describe(index="رقم العنصر (من /queue)")
    async def jump(self, i: discord.Interaction, index: int):
        st = self._st(i.guild_id)
        pos = index - st["index"] - 1
        if pos < 0 or pos >= len(st["queue"]):
            return await i.response.send_message("❌ رقم غير صالح.", ephemeral=True)
        for _ in range(pos):
            st["queue"].append(st["queue"].popleft())
        if st["vc"]: st["vc"].stop()
        await i.response.send_message(f"⏩ انتقلنا إلى {index}.", ephemeral=True)

    @app_commands.command(name="restart", description="العودة إلى أول المقطع")
    async def restart(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        if st["index"] == 1:
            return await i.response.send_message("🔄 بالفعل عند البداية.", ephemeral=True)
        # أعد العناصر السابقة إلى النهاية
        for _ in range(st["index"] - 1):
            st["queue"].appendleft(st["queue"].pop())
        st["index"] = 0
        if st["vc"]: st["vc"].stop()
        await i.response.send_message("⏮️ الرجوع إلى البداية.", ephemeral=True)

    # ---------- أمر stream ----------
    @app_commands.command(name="stream", description="أضف رابط MP3 أو يوتيوب (فيديو/Playlist)")
    @app_commands.describe(url="الرابط")
    async def stream(self, i: discord.Interaction, url: str):
        if not i.user.voice or not i.user.voice.channel:
            return await i.response.send_message("🚫 انضم إلى قناة صوتية.", ephemeral=True)
        await i.response.defer(thinking=True)

        st   = self._st(i.guild_id)
        res  = await self.dl.download(url)

        if isinstance(res, list):                 # Playlist
            st["queue"].extend(res)
            await i.followup.send(f"📜 أضفنا {len(res)} مقطعاً.", ephemeral=True)
        else:                                     # عنصر مفرد
            st["queue"].append(res)
            await i.followup.send("✅ أُضيف للطابور.", ephemeral=True)

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await i.user.voice.channel.connect()
        if not st["current"]:
            await self._next(i, first=True)

    # ---------- أوامر التحكم ----------
    @app_commands.command(name="play", description="تشغيل/استئناف")
    async def play(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            return await i.response.send_message("▶️ استئناف.", ephemeral=True)
        if (not vc or not vc.is_playing()) and st["queue"]:
            await i.response.defer(thinking=True)
            await self._next(i)
            return
        await i.response.send_message("لا شيء لتشغيله.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            return await i.response.send_message("⏸️ تم الإيقاف.", ephemeral=True)
        await i.response.send_message("⏸️ لا شيء يعمل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المقطع الحالي")
    async def skip(self, i: discord.Interaction):
        st, vc = self._st(i.guild_id), None
        vc = st["vc"]
        if vc and vc.is_playing():
            vc.stop()
            return await i.response.send_message("⏭️ تم التخطي.", ephemeral=True)
        await i.response.send_message("⏭️ لا شيء يُشغّل.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, i: discord.Interaction):
        await i.response.send_message("⏹️ تم الإيقاف.", ephemeral=True)
        st = self._st(i.guild_id)
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        st["queue"].clear()
        st.update(index=0, current=None)
        if st["timer"]: st["timer"].cancel()

    # ---------- تشغيل وتسلسل ----------
    async def _next(self, i: discord.Interaction, first=False):
        st = self._st(i.guild_id)
        if st["timer"]: st["timer"].cancel()
        if not st["queue"]:
            if st["vc"]: await st["vc"].disconnect()
            st.update(current=None)
            return

        elem = st["queue"].popleft()
        st["index"] += 1
        # تنزيل إذا كان رابط فيديو
        if "path" in elem:
            path, title = elem["path"], elem["title"]
        elif elem["url"].startswith("http"):
            dl = await self.dl.download(elem["url"])
            path, title = dl["path"], dl["title"]
        else:  # احتياطي
            path, title = elem, Path(elem).name

        st["current"] = {"path": path, "title": title}

        # تنزيل المقطع التالي مسبقاً
        if st["queue"]:
            nxt = st["queue"][0]
            if "url" in nxt:
                st["download_task"] = asyncio.create_task(self.dl.download(nxt["url"]))

        src = discord.FFmpegOpusAudio(path, executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin", options="-vn")
        st["vc"].play(src, after=lambda e: self.bot.loop.create_task(self._after(i, e)))

        dur   = int(MP3(path).info.length)
        embed = discord.Embed(title=title, color=0x2ecc71)
        embed.set_footer(text=f"المقطع رقم {st['index']}")
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)
        embed.add_field(name="بقية الطابور", value=str(len(st["queue"])), inline=True)

        if first:
            st["msg"] = await i.followup.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        st["timer"] = self.bot.loop.create_task(self._ticker(i.guild_id, dur))

    async def _after(self, i: discord.Interaction, err):
        if err: self.logger.error(f"خطأ: {err}", exc_info=True)
        await self._next(i)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["msg"].embeds[0]
            embed.set_field_at(2, name="المنقضي", value=self._fmt(elapsed), inline=True)
            await st["msg"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
