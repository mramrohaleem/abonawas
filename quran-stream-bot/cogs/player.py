# cogs/player.py
import asyncio
import re
import discord
from dataclasses import dataclass, field
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from mutagen.mp3 import MP3

from modules.logger_config  import setup_logger
from modules.downloader     import Downloader
from modules.playlist_store import PlaylistStore

_RX_URL = re.compile(r"https?://", re.I)


# ---------- حالة كل Guild ---------- #
@dataclass
class GuildState:
    playlist:      list[dict]               = field(default_factory=list)
    index:         int                      = -1
    vc:            discord.VoiceClient | None = None
    msg:           discord.Message  | None  = None
    timer:         asyncio.Task     | None  = None
    prefetch_task: asyncio.Task     | None  = None


# ---------- Player Cog ---------- #
class Player(commands.Cog):
    """بثّ تلاوات + يوتيوب/فيسبوك + قوائم مفضّلة."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger(__name__)
        self.dl      = Downloader(self.logger)
        self.store   = PlaylistStore()
        self.states: dict[int, GuildState] = {}

    # ــــــــ أدوات مساعدة ــــــــ #
    def _st(self, gid: int) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3600)
        m, s   = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(text: str) -> bool:
        return bool(_RX_URL.match(text or ""))

    # ---------- التأكد من الاتصال الصوتي ---------- #
    async def _ensure_voice(self, interaction: discord.Interaction) -> bool:
        """
        يحاول إبقاء الـ VoiceClient متصلاً. يرجع True إذا أصبح متصلاً،
        وإلا False (مثلاً إن لم يكن المستخدم في أي قناة).
        """
        st = self._st(interaction.guild_id)

        # ما زال متصلاً وسليم؟
        if st.vc and st.vc.is_connected():
            return True

        # القناة التي يجب أن نتصل بها:
        channel: discord.VoiceChannel | None = None
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
        elif st.vc:                         # أعد محاولة الاتصال بنفس القناة السابقة
            channel = st.vc.channel         # type: ignore

        if not channel:
            return False                    # لا توجد قناة يمكن الاتصال بها

        try:
            st.vc = await channel.connect()
            return True
        except discord.ClientException as e:
            self.logger.warning(f"تعذّر الاتصال بالصوت: {e}")
            return False

    # ---------- البحث فى يوتيوب / فيسبوك ---------- #
    async def _yt_search(self, query: str) -> list[dict]:
        from yt_dlp import YoutubeDL
        opts = {
            "quiet": True,
            "extract_flat": False,
            "skip_download": True,
            "format": "bestaudio/best",
        }
        try:
            data = await asyncio.to_thread(
                lambda: YoutubeDL(opts).extract_info(
                    f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False)
            )
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
            self.logger.error(f"[بحث] {exc}", exc_info=True)
            return []

    # ════════════════════════════════════════════════
    #                 قوائم المفضّلة
    # ════════════════════════════════════════════════
    @app_commands.command(name="fav-save", description="حفظ الطابور كقائمة مفضّلة")
    async def fav_save(self, interaction: discord.Interaction, name: str):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        urls = [itm["url"] for itm in st.playlist]
        self.store.save(interaction.guild_id, name, urls)
        await interaction.response.send_message(f"✅ تم حفظ القائمة **{name}**.", ephemeral=True)

    @app_commands.command(name="fav-list", description="عرض القوائم المحفوظة")
    async def fav_list(self, interaction: discord.Interaction):
        names = self.store.list_names(interaction.guild_id)
        if not names:
            return await interaction.response.send_message("لا توجد قوائم محفوظة.", ephemeral=True)
        await interaction.response.send_message(
            "القوائم: " + ", ".join(f"`{n}`" for n in names), ephemeral=True
        )

    class _FavSelect(discord.ui.Select):
        def __init__(self, names: list[str], cog: "Player"):
            opts = [discord.SelectOption(label=n, value=n) for n in names]
            super().__init__(placeholder="اختر قائمة", options=opts)
            self.cog = cog

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self.cog._fav_play_exec(interaction, self.values[0])

    @app_commands.command(name="fav-play", description="تشغيل قائمة محفوظة")
    async def fav_play(self, interaction: discord.Interaction):
        names = self.store.list_names(interaction.guild_id)
        if not names:
            return await interaction.response.send_message("لا توجد قوائم.", ephemeral=True)
        view = discord.ui.View()
        view.add_item(self._FavSelect(names, self))
        await interaction.response.send_message("اختر قائمة للتشغيل:", view=view, ephemeral=True)

    async def _fav_play_exec(self, interaction: discord.Interaction, name: str):
        urls = self.store.get(interaction.guild_id, name)
        if not urls:
            return await interaction.followup.send("❌ القائمة غير موجودة.", ephemeral=True)

        st = self._st(interaction.guild_id)
        st.playlist.clear()
        for url in urls:
            st.playlist.append({"url": url})  # التنزيل لاحقًا

        st.index = -1
        await interaction.followup.send(f"📜 تم تحميل قائمة **{name}**.", ephemeral=True)
        if await self._ensure_voice(interaction):
            await self._play_current(interaction)

    # ════════════════════════════════════════════════
    #                    /stream
    # ════════════════════════════════════════════════
    @app_commands.command(name="stream", description="رابط أو كلمات بحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        # المستخدم يجب أن يكون فى قناة صوتيّة
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 انضم إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # (1) رابط مباشر
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # (2) بحث بالكلمات —— النتائج تُعرض فقط لصاحب الأمر (ephemeral)
        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا توجد نتائج.", ephemeral=True)

        # embeds للنتائج
        embeds = []
        for idx, r in enumerate(results, 1):
            emb = discord.Embed(title=r["title"],
                                description=f"المدة: {r['duration']}",
                                color=0x3498db)
            if r["thumb"]:
                emb.set_thumbnail(url=r["thumb"])
            emb.set_footer(text=f"نتيجة {idx}/{len(results)}")
            embeds.append(emb)

        # قائمة منسدلة
        class _SearchSelect(discord.ui.Select):
            def __init__(self, cog: "Player"):
                super().__init__(
                    options=[discord.SelectOption(
                        label=f"{r['title'][:80]} [{r['duration']}]",
                        value=r["url"])
                        for r in results],
                    placeholder="اختر المقطع",
                    min_values=1, max_values=1
                )
                self.cog = cog

            async def callback(self, i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await self.cog._handle_stream(i, self.values[0])
                # تعطيل القائمة بعد الاختيار
                for ch in self.view.children:
                    ch.disabled = True
                await i.message.edit(view=self.view)
                self.view.stop()

        view = discord.ui.View()
        view.add_item(_SearchSelect(self))
        await interaction.followup.send(embeds=embeds, view=view, ephemeral=True)

    # ════════════════════════════════════════════════
    #                أوامر الطابور
    # ════════════════════════════════════════════════
    @app_commands.command(name="queue", description="عرض قائمة التشغيل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        emb = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, itm in enumerate(st.playlist, 1):
            prefix = "▶️" if i-1 == st.index else "  "
            emb.add_field(name=f"{prefix} {i}.", value=itm["title"], inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال لمقطع معيّن")
    async def jump(self, interaction: discord.Interaction, number: int):
        st = self._st(interaction.guild_id)
        if not 1 <= number <= len(st.playlist):
            return await interaction.response.send_message("❌ رقم غير صالح.", ephemeral=True)
        st.index = number - 2
        if st.vc:
            st.vc.stop()
        await interaction.response.send_message(f"⏩ الانتقال إلى {number}.", ephemeral=True)

    @app_commands.command(name="restart", description="العودة للبداية")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st.index = -1
        if st.vc:
            st.vc.stop()
        await interaction.response.send_message("⏮️ عدنا إلى البداية.", ephemeral=True)

    @app_commands.command(name="play", description="تشغيل أو استئناف")
    async def play(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st.vc and st.vc.is_paused():
            st.vc.resume()
            return await interaction.response.send_message("▶️ استئناف.", ephemeral=True)

        if st.playlist and st.index == -1:
            await interaction.response.defer(thinking=True)
            return await self._play_current(interaction)

        await interaction.response.send_message("لا يوجد ما يُشغَّل.", ephemeral=True)

    @app_commands.command(name="pause", description="إيقاف مؤقت")
    async def pause(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if st.vc and st.vc.is_playing():
            st.vc.pause()
            return await interaction.response.send_message("⏸️ إيقاف مؤقت.", ephemeral=True)
        await interaction.response.send_message("⏸️ لا شيء يعمل.", ephemeral=True)

    @app_commands.command(name="skip", description="تخطي الحالي")
    async def skip(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st.index = (st.index + 1) % len(st.playlist)
        if st.vc:
            st.vc.stop()
        await interaction.response.send_message("⏭️ تم التخطي.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st.playlist.clear()
        st.index = -1
        if st.vc:
            st.vc.stop()
            await st.vc.disconnect()
            st.vc = None           # <— مسح المرجع لمنع استعماله لاحقًا
        if st.timer:
            st.timer.cancel()
        await interaction.response.send_message("⏹️ توقّف كل شيء.", ephemeral=True)

    # ═══════════════════════════════════════
    #           تشغيل داخلى
    # ═══════════════════════════════════════
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        try:
            res = await self.dl.download(url)
        except Exception:
            return await interaction.followup.send("⚠️ المقطع غير متاح أو محجوب.", ephemeral=True)

        if isinstance(res, list):
            st.playlist.extend(res)
            msg = f"📜 أضيف {len(res)} مقاطع."
        else:
            st.playlist.append(res)
            msg = "✅ أضيف المقطع."

        await interaction.followup.send(msg, ephemeral=True)
        if await self._ensure_voice(interaction):
            if st.index == -1:
                await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            st.index = -1
            return

        # تأكّد أننا متصلون قبل اللعب
        if not await self._ensure_voice(interaction):
            return

        st.index = (st.index + 1) % len(st.playlist)
        item = st.playlist[st.index]

        if "path" not in item:
            item.update(await self.dl.download(item["url"]))

        # ---- Prefetch الملفين التاليين ----
        async def _prefetch():
            idx = st.index
            tasks = []
            for off in (1, 2):
                nxt = st.playlist[(idx + off) % len(st.playlist)]
                if "url" in nxt and "path" not in nxt:
                    tasks.append(self.dl.download(nxt["url"]))
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        if st.prefetch_task and not st.prefetch_task.done():
            st.prefetch_task.cancel()
        st.prefetch_task = asyncio.create_task(_prefetch())

        # ---- تشغيل ----
        src = discord.FFmpegOpusAudio(
            item["path"],
            executable=self.bot.ffmpeg_exe,
            before_options="-nostdin",
            options="-vn"
        )
        st.vc.play(src, after=lambda e:
                   self.bot.loop.create_task(self._after(interaction, e)))

        # ---- Embed ----
        dur = int(MP3(item["path"]).info.length)
        emb = discord.Embed(title=item["title"], color=0x2ecc71)
        emb.add_field(name="المدة", value=self._fmt(dur))
        emb.set_footer(text=f"{st.index+1}/{len(st.playlist)}")

        if st.msg is None:
            st.msg = await interaction.channel.send(embed=emb)
        else:
            await st.msg.edit(embed=emb)

        if st.timer:
            st.timer.cancel()
        st.timer = self.bot.loop.create_task(self._ticker(interaction.guild_id))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error("FFmpeg/Playback Error", exc_info=True)
        # جرّب إعادة الاتصال لو انقطع
        if await self._ensure_voice(interaction):
            await self._play_current(interaction)

    async def _ticker(self, gid: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st.vc and st.vc.is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            emb = st.msg.embeds[0]
            if len(emb.fields) == 2:
                emb.set_field_at(1, name="المنقضي", value=self._fmt(elapsed))
            else:
                emb.add_field(name="المنقضي", value=self._fmt(elapsed))
            await st.msg.edit(embed=emb)
            await asyncio.sleep(10)


async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
