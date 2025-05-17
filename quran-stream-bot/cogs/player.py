import discord, asyncio, re
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from datetime import datetime
from yt_dlp import YoutubeDL

class Player(commands.Cog):
    """بثّ التلاوات – بحث يوتيوب – إدارة طابور ثابت مع فهرسة."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger()
        self.dl      = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    # ---------- أدوات داخلية ----------
    def _st(self, gid: int):
        """حال السيرفر."""
        return self.states.setdefault(gid, {
            "playlist": [], "index": -1,
            "vc": None, "msg": None, "timer": None, "download_task": None
        })

    @staticmethod
    def _fmt(sec: int):
        m, s = divmod(sec, 60)
        return f"{m:02}:{s:02}"

    @staticmethod
    def _is_url(txt: str) -> bool:
        return re.match(r"https?://", txt or "") is not None

    def _yt_search(self, query: str):
        opts = {
            "quiet": True, "skip_download": True,
            "extract_flat": False, "format": "bestaudio/best",
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch{self.SEARCH_LIMIT}:{query}",
                                        download=False)
            results = []
            for e in info.get("entries", []):
                results.append({
                    "url":  f"https://www.youtube.com/watch?v={e['id']}",
                    "title": e.get("title", "—"),
                    "duration": self._fmt(e.get("duration", 0)),
                    "thumb": e.get("thumbnail")
                })
            return results
        except Exception as exc:
            self.logger.error(f"[يوتيوب] خطأ البحث: {exc}", exc_info=True)
            return []

    # ---------- واجهة البحث ----------
    class _SearchSelect(discord.ui.Select):
        def __init__(self, results: list[dict], cog: "Player"):
            self.cog = cog
            opts = [
                discord.SelectOption(
                    label=f"{r['title'][:80]} [{r['duration']}]",
                    value=r["url"]
                ) for r in results
            ]
            super().__init__(
                placeholder="اختر المقطع المطلوب",
                min_values=1, max_values=1, options=opts
            )

        async def callback(self, interaction: discord.Interaction):
            url = self.values[0]
            await self.cog._handle_stream(interaction, url)
            await interaction.message.edit(view=None)
            self.view.stop()

    class _SearchView(discord.ui.View):
        def __init__(self, results: list[dict], cog: "Player"):
            super().__init__(timeout=60)
            self.add_item(Player._SearchSelect(results, cog))

    # ---------- /stream ----------
    @app_commands.command(name="stream",
                          description="رابط يوتيوب/MP3 أو كلمات للبحث")
    @app_commands.describe(input="الرابط أو كلمات البحث")
    async def stream(self, interaction: discord.Interaction, input: str):

        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 يجب الانضمام لقناة صوتية أولاً.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # إذا كان رابطًا
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث بالكلمات
        results = await asyncio.to_thread(self._yt_search, input)
        if not results:
            return await interaction.followup.send(
                "❌ لا نتائج لهذا البحث.", ephemeral=True)

        view = self._SearchView(results, self)
        embed = discord.Embed(title="نتائج البحث",
                              description=f"اختر من أول {len(results)} نتائج:",
                              color=0x3498db)
        for i, r in enumerate(results, 1):
            embed.add_field(
                name=f"{i}. {r['title']} ({r['duration']})",
                value=f"[الرابط]({r['url']})",
                inline=False
            )
        if results[0]["thumb"]:
            embed.set_thumbnail(url=results[0]["thumb"])

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    # ---------- أوامر الطابور / التحكم ----------
    @app_commands.command(name="queue", description="عرض الطابور")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, it in enumerate(st["playlist"], 1):
            prefix = "▶️" if i-1 == st["index"] else "  "
            embed.add_field(name=f"{prefix} {i}.", value=it["title"],
                            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="انتقال لرقم معيّن")
    async def jump(self, interaction: discord.Interaction, number: int):
        st = self._st(interaction.guild_id)
        if not 1 <= number <= len(st["playlist"]):
            return await interaction.response.send_message(
                "❌ رقم غير صالح.", ephemeral=True)
        st["index"] = number - 2
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message(
            f"⏩ الانتقال إلى {number}.", ephemeral=True)

    @app_commands.command(name="restart", description="إعادة من البداية")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = -1
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message("⏮️ رجعنا للبداية.", ephemeral=True)

    @app_commands.command(name="play", description="تشغيل/استئناف")
    async def play(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st["vc"] and st["vc"].is_paused():
            st["vc"].resume()
            return await interaction.response.send_message("▶️ استئناف.", ephemeral=True)
        if st["playlist"]:
            await interaction.response.defer(thinking=True)
            if st["index"] == -1:
                await self._play_current(interaction)
            else:
                st["vc"].resume() if st["vc"] else None
            return
        await interaction.response.send_message("لا شيء في الطابور.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st["vc"] and st["vc"].is_playing():
            st["vc"].pause()
            return await interaction.response.send_message("⏸️ موقوف مؤقتًا.", ephemeral=True)
        await interaction.response.send_message("لا يوجد تشغيل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي الحالي")
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
        st["playlist"].clear(); st["index"] = -1
        if st["vc"]:
            st["vc"].stop(); await st["vc"].disconnect()
        if st["timer"]: st["timer"].cancel()
        await interaction.response.send_message("⏹️ الطابور أُفرِغ.", ephemeral=True)

    # ---------- منطق التشغيل الداخلي ----------
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        res = await self.dl.download(url)
        if isinstance(res, list):
            st["playlist"].extend(res)
            msg = f"📜 أُضيف {len(res)} مقاطع."
        else:
            st["playlist"].append(res)
            msg = "✅ أُضيف المقطع."
        await interaction.followup.send(msg, ephemeral=True)

        if not st["vc"]:
            st["vc"] = await interaction.user.voice.channel.connect()
        if st["index"] == -1:
            await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st["index"] = (st["index"] + 1) % len(st["playlist"])
        item = st["playlist"][st["index"]]

        if "path" not in item:                # لو لم يُنزَّل بعد
            item.update(await self.dl.download(item["url"]))

        # تنزيل المقطع التالي مسبقًا
        nxt = st["playlist"][(st["index"] + 1) % len(st["playlist"])]
        if "url" in nxt and "path" not in nxt:
            st["download_task"] = asyncio.create_task(self.dl.download(nxt["url"]))

        # تشغيل
        src = discord.FFmpegOpusAudio(item["path"],
                                      executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin", options="-vn")
        st["vc"].play(src, after=lambda e:
                      self.bot.loop.create_task(self._after(interaction, e)))

        # Embed المعلومات
        dur = int(MP3(item["path"]).info.length)
        embed = discord.Embed(title=item["title"], color=0x2ecc71)
        embed.add_field(name="المدة", value=self._fmt(dur))
        embed.set_footer(
            text=f"{st['index']+1}/{len(st['playlist'])}"
        )
        if st["msg"] is None:
            st["msg"] = await interaction.channel.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        # عدّاد الزمن
        if st["timer"]: st["timer"].cancel()
        st["timer"] = self.bot.loop.create_task(self._ticker(interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error(f"خطأ التشغيل: {err}", exc_info=True)
        await self._play_current(interaction)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid); start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["msg"].embeds[0]
            if len(embed.fields) == 2:
                embed.set_field_at(1, name="المنقضي", value=self._fmt(elapsed))
            else:
                embed.add_field(name="المنقضي", value=self._fmt(elapsed))
            await st["msg"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
