# cogs/player.py

import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from pathlib import Path
from datetime import datetime
from yt_dlp import YoutubeDL

class Player(commands.Cog):
    """بث تلاوات وYouTube Search مع إدارة طابور ثابت وفهرسة وخصائص متقدمة."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger()
        self.dl     = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    def _st(self, gid: int):
        return self.states.setdefault(gid, {
            "playlist": [],
            "index": -1,
            "vc": None,
            "msg": None,
            "timer": None,
            "download_task": None
        })

    def _fmt(self, sec: int):
        m, s = divmod(sec, 60)
        return f"{m:02}:{s:02}"

    @staticmethod
    def _is_url(inp: str) -> bool:
        return inp.startswith("http://") or inp.startswith("https://")

    def _yt_search(self, query: str):
        opts = {
            "quiet": True,
            "extract_flat": False,
            "skip_download": True,
            "format": "bestaudio/best",
        }
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False)
            results = []
            for entry in info["entries"]:
                duration = entry.get("duration", 0)
                thumbnail = entry.get("thumbnail")
                title = entry.get("title", "—")
                url = f"https://www.youtube.com/watch?v={entry['id']}"
                results.append({
                    "url": url,
                    "title": title,
                    "duration": self._fmt(duration),
                    "thumbnail": thumbnail
                })
            return results

    class _StreamSearchView(discord.ui.View):
        def __init__(self, results, cog: "Player"):
            super().__init__(timeout=60)
            self.cog = cog
            self.options = [
                discord.SelectOption(
                    label=r["title"][:100],
                    description=f"⏱️ {r['duration']}",
                    value=r["url"]
                )
                for r in results
            ]
            self.add_item(discord.ui.Select(
                placeholder="اختر مقطعًا لإضافته للطابور",
                min_values=1,
                max_values=1,
                options=self.options
            ))

        @discord.ui.select()
        async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
            url = select.values[0]
            await interaction.response.defer(ephemeral=True)  # حل مشكلة interaction failed
            await self.cog._handle_stream(interaction, url)
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)
            self.stop()

    # ----------- أوامر البوت ------------

    @app_commands.command(
        name="stream",
        description="أضف رابط MP3/YouTube أو ابحث بكلمات"
    )
    @app_commands.describe(input="رابط أو كلمات البحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        if not (voice := interaction.user.voice) or not voice.channel:
            return await interaction.response.send_message(
                "🚫 عليك الانضمام إلى قناة صوتية أولاً.", ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث في YouTube
        results = await asyncio.to_thread(self._yt_search, input)
        if not results:
            return await interaction.followup.send("❌ لم أجد أي نتائج.", ephemeral=True)

        view = self._StreamSearchView(results, self)
        embed = discord.Embed(
            title="نتائج البحث",
            description=f"اختر مقطعاً من أول {self.SEARCH_LIMIT} نتائج:",
            color=discord.Color.blue()
        )
        for idx, r in enumerate(results, 1):
            embed.add_field(
                name=f"{idx}. {r['title']}",
                value=f"[رابط]({r['url']}) - ⏱️ {r['duration']}",
                inline=False
            )
        if results and results[0].get("thumbnail"):
            embed.set_thumbnail(url=results[0]["thumbnail"])

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="queue", description="عرض قائمة التشغيل بالكامل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x3498db)
        for idx, item in enumerate(st["playlist"], start=1):
            prefix = "▶️" if idx-1 == st["index"] else "  "
            embed.add_field(name=f"{prefix} {idx}.", value=item["title"], inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال إلى مقطع معيّن")
    @app_commands.describe(number="رقم المقطع (1=الأول)")
    async def jump(self, interaction: discord.Interaction, number: int):
        st = self._st(interaction.guild_id)
        length = len(st["playlist"])
        if number < 1 or number > length:
            return await interaction.response.send_message("❌ رقم غير صالح.", ephemeral=True)

        st["index"] = number - 2
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message(f"⏩ انتقلنا إلى {number}.", ephemeral=True)

    @app_commands.command(name="restart", description="العودة إلى المقطع الأوّل")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = -1
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message("⏮️ عدنا إلى البداية.", ephemeral=True)

    @app_commands.command(name="play", description="تشغيل/استئناف")
    async def play(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            return await interaction.response.send_message("▶️ استئناف.", ephemeral=True)
        if (not vc or not vc.is_playing()) and st["playlist"]:
            await interaction.response.defer(thinking=True)
            if st["index"] == -1:
                await self._play_current(interaction)
            else:
                vc.resume() if vc else None
            return
        await interaction.response.send_message("لا يوجد ما يتم تشغيله.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id); vc = st["vc"]
        if vc and vc.is_playing():
            vc.pause()
            return await interaction.response.send_message("⏸️ تم الإيقاف مؤقتًا.", ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يعمل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي المقطع الحالي")
    async def skip(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = (st["index"] + 1) % len(st["playlist"])
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message("⏭️ تم التخطي.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st["playlist"].clear()
        st["index"] = -1
        if st["vc"]:
            st["vc"].stop()
            await st["vc"].disconnect()
        if st["timer"]:
            st["timer"].cancel()
        await interaction.response.send_message("⏹️ تم الإيقاف ومسح الطابور.", ephemeral=True)

    # ----------- Internal Playback ------------

    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        result = await self.dl.download(url)
        if isinstance(result, list):
            st["playlist"].extend(result)
            await interaction.followup.send(f"📜 أُضيف {len(result)} مقطعًا.", ephemeral=True)
        else:
            st["playlist"].append(result)
            await interaction.followup.send("✅ أُضيف للطابور.", ephemeral=True)

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()

        if st["index"] == -1:
            await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st["index"] = (st["index"] + 1) % len(st["playlist"])
        elem = st["playlist"][st["index"]]

        if "path" not in elem:
            dl = await self.dl.download(elem["url"])
            elem.update(dl)

        path, title = elem["path"], elem["title"]

        nxt = st["playlist"][(st["index"] + 1) % len(st["playlist"])]
        if "url" in nxt and "path" not in nxt:
            st["download_task"] = asyncio.create_task(self.dl.download(nxt["url"]))

        src = discord.FFmpegOpusAudio(
            path, executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn"
        )
        st["vc"].play(src, after=lambda e: self.bot.loop.create_task(self._after(interaction, e)))

        dur = int(MP3(path).info.length)
        embed = discord.Embed(title=title, color=0x2ecc71)
        embed.set_footer(text=f"المقطع {st['index']+1}/{len(st['playlist'])}")
        embed.add_field(name="المدة", value=self._fmt(dur), inline=True)

        ch = interaction.channel
        if st["msg"] is None:
            st["msg"] = await ch.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        if st["timer"]:
            st["timer"].cancel()
        st["timer"] = self.bot.loop.create_task(self._ticker(interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error(f"Playback error: {err}", exc_info=True)
        await self._play_current(interaction)

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
