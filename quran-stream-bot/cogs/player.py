# cogs/player.py
import discord, asyncio, re
from discord import app_commands
from discord.ext import commands
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from mutagen.mp3 import MP3
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from yt_dlp.utils import DownloadError

_RX_URL = re.compile(r"https?://", re.I)

# ---------- نموذج حالة كل Guild ---------- #
@dataclass
class GuildState:
    playlist:      list[dict] = field(default_factory=list)
    index:         int        = -1
    vc:            discord.VoiceClient | None = None
    msg:           discord.Message     | None = None
    timer:         asyncio.Task        | None = None
    download_task: asyncio.Task        | None = None

# ------------------------------------------------ #
class Player(commands.Cog):
    """بث تلاوات – بحث يوتيوب – طابور ثابت مع تحكّم كامل."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger(__name__)
        self.dl      = Downloader(self.logger)
        self.states: dict[int, GuildState] = {}

    # ---------- أدوات مساعدة ---------- #
    def _st(self, gid: int) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3600); m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(text: str) -> bool:
        return bool(_RX_URL.match(text or ""))

    # ---------- البحث في يوتيوب (تلخيص النتيجة) ---------- #
    async def _yt_search(self, query: str) -> list[dict]:
        from yt_dlp import YoutubeDL
        opts = {"quiet": True, "extract_flat": False, "skip_download": True,
                "format": "bestaudio/best"}
        try:
            data = await asyncio.to_thread(
                lambda: YoutubeDL(opts).extract_info(
                    f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False))
            results = []
            for e in data.get("entries", []):
                results.append({
                    "url":   f"https://www.youtube.com/watch?v={e['id']}",
                    "title": e.get("title", "—"),
                    "duration": self._fmt(e.get("duration", 0)),
                    "thumb": e.get("thumbnail")
                })
            return results
        except DownloadError as de:   # مثلاً فيديو محجوب جغرافيّاً
            self.logger.warning(f"[يوتيوب] لا نتائج: {de}")
            return []
        except Exception as exc:
            self.logger.error(f"[يوتيوب] خطأ البحث: {exc}", exc_info=True)
            return []

    # ---------- عناصر واجهة البحث ---------- #
    class _Select(discord.ui.Select):
        def __init__(self, results: list[dict], cog: "Player"):
            self.cog = cog
            opts = [discord.SelectOption(
                        label=f"{r['title'][:80]} [{r['duration']}]",
                        value=r["url"])
                    for r in results]
            super().__init__(placeholder="اختر المقطع", min_values=1,
                             max_values=1, options=opts)

        async def callback(self, interaction: discord.Interaction):
            # منع Interaction-Failed
            await interaction.response.defer(ephemeral=True, thinking=False)
            await self.cog._handle_stream(interaction, self.values[0])
            for child in self.view.children: child.disabled = True
            await interaction.message.edit(view=self.view)
            self.view.stop()

    class _View(discord.ui.View):
        def __init__(self, results: list[dict], cog: "Player"):
            super().__init__(timeout=60)
            self.add_item(Player._Select(results, cog))

    # ---------- أمر /stream ---------- #
    @app_commands.command(name="stream",
                          description="رابط YouTube/MP3 أو كلمات للبحث")
    async def stream(self, interaction: discord.Interaction,
                     input: str):
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 انضم إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # رابط مباشر
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث كلمات
        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا توجد نتائج.",
                                                   ephemeral=True)

        embeds: list[discord.Embed] = []
        for i, r in enumerate(results, 1):
            emb = (discord.Embed(title=r["title"],
                                 description=f"المدة: {r['duration']}",
                                 color=0x3498db)
                   .set_footer(text=f"نتيجة {i}/{len(results)}"))
            if r["thumb"]: emb.set_thumbnail(url=r["thumb"])
            embeds.append(emb)

        await interaction.followup.send(embeds=embeds,
                                        view=Player._View(results, self),
                                        ephemeral=True)

    # ---------- أوامر الطابور ---------- #
    @app_commands.command(name="queue", description="عرض قائمة التشغيل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.",
                                                           ephemeral=True)

        emb = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, itm in enumerate(st.playlist, 1):
            prefix = "▶️" if i-1 == st.index else "  "
            emb.add_field(name=f"{prefix} {i}.", value=itm["title"],
                          inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال لمقطع معيّن")
    async def jump(self, interaction: discord.Interaction, number: int):
        st = self._st(interaction.guild_id)
        if not 1 <= number <= len(st.playlist):
            return await interaction.response.send_message("❌ رقم غير صالح.",
                                                           ephemeral=True)
        st.index = number - 2
        if st.vc: st.vc.stop()
        await interaction.response.send_message(f"⏩ الانتقال إلى {number}.",
                                                ephemeral=True)

    @app_commands.command(name="restart", description="العودة للبداية")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.",
                                                           ephemeral=True)
        st.index = -1
        if st.vc: st.vc.stop()
        await interaction.response.send_message("⏮️ عدنا إلى البداية.",
                                                ephemeral=True)

    # --- Play / Pause / Skip / Stop --- #
    @app_commands.command(name="play", description="تشغيل أو استئناف")
    async def play(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st.vc and st.vc.is_paused():
            st.vc.resume()
            return await interaction.response.send_message("▶️ استئناف.",
                                                           ephemeral=True)
        if st.playlist and st.index == -1:
            await interaction.response.defer(thinking=True)
            return await self._play_current(interaction)
        await interaction.response.send_message("لا يوجد ما يُشغَّل.",
                                                ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st.vc and st.vc.is_playing():
            st.vc.pause()
            return await interaction.response.send_message("⏸️ إيقاف مؤقت.",
                                                           ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يعمل.",
                                                ephemeral=True)

    @app_commands.command(name="skip", description="تخطي الحالي")
    async def skip(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.",
                                                           ephemeral=True)
        st.index = (st.index + 1) % len(st.playlist)
        if st.vc: st.vc.stop()
        await interaction.response.send_message("⏭️ تم التخطي.",
                                                ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف الطابور")
    async def stop(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st.playlist.clear(); st.index = -1
        if st.vc: st.vc.stop(); await st.vc.disconnect()
        if st.timer: st.timer.cancel()
        await interaction.response.send_message("⏹️ توقّف كل شيء.",
                                                ephemeral=True)

    # ---------- تشغيل داخلي ---------- #
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        try:
            res = await self.dl.download(url)
        except Exception:
            return await interaction.followup.send("⚠️ المقطع غير متاح أو محجوب.",
                                                   ephemeral=True)

        if isinstance(res, list):
            st.playlist.extend(res);   msg = f"📜 أضيف {len(res)} مقاطع."
        else:
            st.playlist.append(res);   msg = "✅ أضيف المقطع."

        await interaction.followup.send(msg, ephemeral=True)

        if not st.vc:
            st.vc = await interaction.user.voice.channel.connect()
        if st.index == -1:
            await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:   # طابور فارغ بعد حذف المقطع الأخير
            st.index = -1
            return

        st.index = (st.index + 1) % len(st.playlist)
        item = st.playlist[st.index]
        if "path" not in item:
            item.update(await self.dl.download(item["url"]))

        # prefetch
        nxt = st.playlist[(st.index + 1) % len(st.playlist)]
        if "url" in nxt and "path" not in nxt and not st.download_task:
            st.download_task = asyncio.create_task(
                self.dl.download(nxt["url"]))

        # التشغيل
        src = discord.FFmpegOpusAudio(
            item["path"], executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn")
        st.vc.play(src,
                   after=lambda e:
                     self.bot.loop.create_task(self._after(interaction, e)))

        # Embed
        dur = int(MP3(item["path"]).info.length)
        emb = discord.Embed(title=item["title"], color=0x2ecc71)
        emb.add_field(name="المدة", value=self._fmt(dur))
        emb.set_footer(text=f"{st.index+1}/{len(st.playlist)}")
        if st.msg is None:
            st.msg = await interaction.channel.send(embed=emb)
        else:
            await st.msg.edit(embed=emb)

        if st.timer: st.timer.cancel()
        st.timer = self.bot.loop.create_task(
            self._ticker(interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error(f"خطأ التشغيل: {err}", exc_info=True)
        await self._play_current(interaction)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st.vc and st.vc.is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            emb = st.msg.embeds[0]
            if len(emb.fields) == 2:
                emb.set_field_at(1, name="المنقضي",
                                 value=self._fmt(elapsed))
            else:
                emb.add_field(name="المنقضي",
                              value=self._fmt(elapsed))
            await st.msg.edit(embed=emb)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
