import discord, asyncio, re
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from datetime import datetime
from yt_dlp import YoutubeDL

class Player(commands.Cog):
    """بث تلاوات – بحث يوتيوب – طابور ثابت مع تحكّم كامل."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger()
        self.dl     = Downloader(self.logger)
        self.states: dict[int, dict] = {}

    # --------- أدوات داخلية ---------
    def _st(self, gid: int):
        return self.states.setdefault(gid, {
            "playlist": [], "index": -1,
            "vc": None, "msg": None,
            "timer": None, "download_task": None
        })

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(text: str) -> bool:
        return bool(re.match(r"https?://", text or ""))

    # --------- البحث في يوتيوب ---------
    def _yt_search(self, query: str):
        opts = {
            "quiet": True,
            "extract_flat": False,
            "skip_download": True,
            "format": "bestaudio/best",
        }
        try:
            with YoutubeDL(opts) as ydl:
                data = ydl.extract_info(
                    f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False)
            results = []
            for e in data.get("entries", []):
                results.append({
                    "url":      f"https://www.youtube.com/watch?v={e['id']}",
                    "title":    e.get("title", "—"),
                    "duration": self._fmt(e.get("duration", 0)),
                    "thumb":    e.get("thumbnail")
                })
            return results
        except Exception as exc:
            self.logger.error(f"[يوتيوب] خطأ البحث: {exc}", exc_info=True)
            return []

    # --------- القائمة المنسدلة ---------
    class _SearchSelect(discord.ui.Select):
        def __init__(self, results: list[dict], cog: "Player"):
            self.cog = cog
            options = [
                discord.SelectOption(
                    label=f"{r['title'][:80]} [{r['duration']}]",
                    value=r["url"]
                ) for r in results
            ]
            super().__init__(
                placeholder="اختر المقطع المطلوب",
                min_values=1, max_values=1,
                options=options
            )

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)  # يمنع “Interaction failed”
            await self.cog._handle_stream(interaction, self.values[0])
            # تعطيل القائمة بعد الاختيار
            for child in self.view.children:
                child.disabled = True
            await interaction.message.edit(view=self.view)
            self.view.stop()

    class _SearchView(discord.ui.View):
        def __init__(self, results: list[dict], cog: "Player"):
            super().__init__(timeout=60)
            self.add_item(Player._SearchSelect(results, cog))

    # --------- /stream ---------
    @app_commands.command(name="stream",
                          description="رابط YouTube/MP3 أو كلمات للبحث")
    @app_commands.describe(input="الرابط أو كلمات البحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        # يجب أن يكون المستخدم في قناة صوتية
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 عليك الانضمام إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # إن كان رابطًا مباشرًا
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث بالكلمات
        results = await asyncio.to_thread(self._yt_search, input)
        if not results:
            return await interaction.followup.send(
                "❌ لا توجد نتائج.", ephemeral=True)

        view = self._SearchView(results, self)

        # نرسل عدّة Embeds كلٌّ بصورته المصغّرة
        embeds: list[discord.Embed] = []
        for idx, r in enumerate(results, 1):
            emb = discord.Embed(
                title=r["title"],
                description=f"المدة: {r['duration']}",
                color=0x3498db
            )
            if r["thumb"]:
                emb.set_thumbnail(url=r["thumb"])
            emb.set_footer(text=f"نتيجة {idx}/{len(results)}")
            embeds.append(emb)

        await interaction.followup.send(embeds=embeds, view=view, ephemeral=True)

    # --------- أوامر الطابور والتحكّم ---------
    @app_commands.command(name="queue", description="عرض قائمة التشغيل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, itm in enumerate(st["playlist"], 1):
            prefix = "▶️" if i-1 == st["index"] else "  "
            embed.add_field(name=f"{prefix} {i}.", value=itm["title"],
                            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال لمقطع محدّد")
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

    @app_commands.command(name="restart", description="العودة للبداية")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = -1
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message(
            "⏮️ عدنا إلى المقطع الأول.", ephemeral=True)

    @app_commands.command(name="play", description="تشغيل/استئناف")
    async def play(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        vc = st["vc"]
        if vc and vc.is_paused():
            vc.resume()
            return await interaction.response.send_message("▶️ استئناف.", ephemeral=True)
        if st["playlist"]:
            await interaction.response.defer(thinking=True)
            if st["index"] == -1:
                await self._play_current(interaction)
            else:
                if vc: vc.resume()
            return
        await interaction.response.send_message("لا يوجد ما يُشغَّل.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st["vc"] and st["vc"].is_playing():
            st["vc"].pause()
            return await interaction.response.send_message("⏸️ تم الإيقاف مؤقتًا.", ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يعمل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي الحالي")
    async def skip(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st["playlist"]:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)
        st["index"] = (st["index"] + 1) % len(st["playlist"])
        if st["vc"]:
            st["vc"].stop()
        await interaction.response.send_message("⏭️ تخطّينا.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st["playlist"].clear(); st["index"] = -1
        if st["vc"]:
            st["vc"].stop(); await st["vc"].disconnect()
        if st["timer"]: st["timer"].cancel()
        await interaction.response.send_message("⏹️ توقّف كل شيء.", ephemeral=True)

    # --------- التشغيل الداخلي ---------
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        res = await self.dl.download(url)
        if isinstance(res, list):
            st["playlist"].extend(res); msg = f"📜 أُضيف {len(res)} مقاطع."
        else:
            st["playlist"].append(res);  msg = "✅ أُضيف المقطع."
        await interaction.followup.send(msg, ephemeral=True)
        if not st["vc"]:
            st["vc"] = await interaction.user.voice.channel.connect()
        if st["index"] == -1:
            await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)

        # ✋ تحقق أولًا: إذا كان الطابور فارغًا، أنهِ التشغيل بلباقة
        if not st["playlist"]:
            st["index"] = -1
            if st["vc"]:
                await st["vc"].disconnect()
                st["vc"] = None
            if st["msg"]:
                await st["msg"].edit(content="🏁 انتهى الطابور.", embed=None)
                st["msg"] = None
            return

        # تدرّج إلى المقطع التالي
        st["index"] = (st["index"] + 1) % len(st["playlist"])
        item = st["playlist"][st["index"]]

        if "path" not in item:
            item.update(await self.dl.download(item["url"]))

        # تنزيل مسبق للمقطع التالي
        nxt = st["playlist"][(st["index"] + 1) % len(st["playlist"])]
        if "url" in nxt and "path" not in nxt:
            st["download_task"] = asyncio.create_task(self.dl.download(nxt["url"]))

        # تشغيل
        src = discord.FFmpegOpusAudio(
            item["path"], executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn"
        )
        st["vc"].play(src, after=lambda e:
                      self.bot.loop.create_task(self._after(interaction, e)))

        # إعداد الـ embed
        dur = int(MP3(item["path"]).info.length)
        embed = discord.Embed(title=item["title"], color=0x2ecc71)
        embed.add_field(name="المدة", value=self._fmt(dur))
        embed.set_footer(text=f"{st['index']+1}/{len(st['playlist'])}")

        if st["msg"] is None:
            st["msg"] = await interaction.channel.send(embed=embed)
        else:
            await st["msg"].edit(embed=embed)

        # مؤقت للتحديث
        if st["timer"]:
            st["timer"].cancel()
        st["timer"] = self.bot.loop.create_task(
            self._ticker(interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error(f"خطأ التشغيل: {err}", exc_info=True)
        await self._play_current(interaction)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st["vc"] and st["vc"].is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st["msg"].embeds[0]
            if len(embed.fields) == 2:
                embed.set_field_at(1, name="المنقضي",
                                   value=self._fmt(elapsed))
            else:
                embed.add_field(name="المنقضي",
                                value=self._fmt(elapsed))
            await st["msg"].edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
