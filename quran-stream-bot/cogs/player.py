# cogs/player.py  –  طابور ثابت + فهرسة بالمؤشر

import discord, asyncio
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from pathlib import Path
from datetime import datetime

class Player(commands.Cog):
    """طابور ثابت يشمل كل المقاطع، مع إمكانيّة القفز لأي رقم."""
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger()
        self.dl     = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    # ---------- أدوات عامّة ----------
    def _st(self, gid: int):
        return self.states.setdefault(gid, {
            "playlist": [],     # قائمة ثابتة [dict]
            "index": -1,        # المؤشّر الحالي (0-based)؛ -1 يعني لا شيء
            "vc": None,
            "timer": None,
            "download_task": None,
            "msg": None
        })
    def _fmt(self, s: int): m, s = divmod(s, 60); return f"{m:02}:{s:02}"

    # ---------- أوامر الطابور ----------
    @app_commands.command(name="queue", description="عرض قائمة التشغيل بالكامل")
    async def queue(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        if not st["playlist"]:
            return await i.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل (ثابتة)", color=0x3498db)
        for n, item in enumerate(st["playlist"], 1):
            prefix = "▶️ " if (n - 1) == st["index"] else "   "
            embed.add_field(name=f"{prefix}{n}.", value=item["title"], inline=False)
        await i.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال إلى رقم مقطع محدّد")
    @app_commands.describe(index="رقم المقطع (1 = الأول)")
    async def jump(self, i: discord.Interaction, index: int):
        st = self._st(i.guild_id)
        if index < 1 or index > len(st["playlist"]):
            return await i.response.send_message("❌ رقم غير صالح.", ephemeral=True)
        st["index"] = index - 2   # -1 ثم سيُزاد +1 في _play_current
        if st["vc"]: st["vc"].stop()
        await i.response.send_message(f"⏩ انتقلنا إلى {index}.", ephemeral=True)

    @app_commands.command(name="restart", description="العودة إلى المقطع الأوّل")
    async def restart(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        if not st["playlist"]:
            return await i.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = -1
        if st["vc"]: st["vc"].stop()
        await i.response.send_message("⏮️ عدنا إلى البداية.", ephemeral=True)

    # ---------- أمر stream (يدعم Playlist) ----------
    @app_commands.command(name="stream", description="إضافة رابط MP3/فيديو/Playlist")
    @app_commands.describe(url="الرابط المطلوب")
    async def stream(self, i: discord.Interaction, url: str):
        if not i.user.voice or not i.user.voice.channel:
            return await i.response.send_message("🚫 انضم إلى قناة صوتية.", ephemeral=True)
        await i.response.defer(thinking=True)

        st = self._st(i.guild_id)
        result = await self.dl.download(url)

        if isinstance(result, list):               # Playlist
            st["playlist"].extend(result)
            await i.followup.send(f"📜 أُضيف {len(result)} مقطعاً.", ephemeral=True)
        else:
            st["playlist"].append(result)
            await i.followup.send("✅ أضيف للطابور.", ephemeral=True)

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await i.user.voice.channel.connect()
        if st["index"] == -1:                      # لم يبدأ شيء بعد
            await self._play_current(i)

    # ---------- أوامر تحكم أساسيّة ----------
    @app_commands.command(name="play", description="تشغيل/استئناف")
    async def play(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            return await i.response.send_message("▶️ استئناف.", ephemeral=True)
        if not vc or not vc.is_playing():
            await i.response.defer(thinking=True)
            if st["index"] == -1 and st["playlist"]:
                await self._play_current(i)
            elif vc:
                vc.resume()
            return
        await i.response.send_message("لا شيء متوقّف.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, i: discord.Interaction):
        st = self._st(i.guild_id); vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            await i.response.send_message("⏸️ تم الإيقاف.", ephemeral=True)
        else:
            await i.response.send_message("⏸️ لا شيء يعمل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المقطع الحالي")
    async def skip(self, i: discord.Interaction):
        st = self._st(i.guild_id); vc = st["vc"]
        if not st["playlist"]:
            return await i.response.send_message("الطابور فارغ.", ephemeral=True)
        st["index"] += 1
        if st["index"] >= len(st["playlist"]):
            st["index"] = 0
        if vc: vc.stop()
        await i.response.send_message("⏭️ تم التخطي.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        st["playlist"].clear(); st["index"] = -1
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        if st["timer"]: st["timer"].cancel()
        await i.response.send_message("⏹️ تم الإيقاف.", ephemeral=True)

    # ---------- التشغيل ----------
    async def _play_current(self, i: discord.Interaction):
        st = self._st(i.guild_id)
        st["index"] += 1
        if st["index"] >= len(st["playlist"]):
            st["index"] = 0
        elem = st["playlist"][st["index"]]

        # إذا كان بحاجة تنزيل
        if "path" not in elem:
            dl = await self.dl.download(elem["url"])
            elem.update(dl)  # يضيف path وtitle

        path, title = elem["path"], elem["title"]

        # تنزيل التالي مسبقاً
        nxt_idx = (st["index"] + 1) % len(st["playlist"])
        nxt = st["playlist"][nxt_idx]
        if "url" in nxt and "path" not in nxt:
            st["download_task"] = asyncio.create_task(self.dl.download(nxt["url"]))

        src = discord.FFmpegOpusAudio(path, executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin", options="-vn")
        st["vc"].play(src, after=lambda e: self.bot.loop.create_task(self._after(i, e)))

        dur = int(MP3(path).info.length)
        embed = discord.Embed(title=title, color=0x2ecc71)
        embed.set_footer(text=f"المقطع رقم {st['index']+1}/{len(st['playlist'])}")
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)

        if st["msg"] is None:
            st["msg"] = await i.followup.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        if st["timer"]: st["timer"].cancel()
        st["timer"] = self.bot.loop.create_task(self._ticker(i.guild_id, dur))

    async def _after(self, i: discord.Interaction, err):
        if err: self.logger.error(f"خطأ: {err}", exc_info=True)
        await self._play_current(i)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid); start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["msg"].embeds[0]
            embed.set_field_at(1, name="المنقضي", value=self._fmt(elapsed), inline=True)
            await st["msg"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
