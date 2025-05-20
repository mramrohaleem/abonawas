# cogs/player.py
import asyncio, re, discord
from dataclasses import dataclass, field
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from mutagen.mp3 import MP3

from modules.logger_config  import setup_logger
from modules.downloader     import Downloader
from modules.playlist_store import PlaylistStore   # ← النسخة الجديدة من المتجر

_RX_URL = re.compile(r"https?://", re.I)


# ────────────────── حالة كل Guild ────────────────── #
@dataclass
class GuildState:
    playlist:      list[dict]               = field(default_factory=list)
    index:         int                      = -1
    vc:            discord.VoiceClient | None = None
    msg:           discord.Message  | None  = None
    timer:         asyncio.Task     | None  = None
    prefetch_task: asyncio.Task     | None  = None


# ────────────────── Player Cog ────────────────── #
class Player(commands.Cog):
    """بثّ تلاوات + إدارة قوائم تشغيل مخصّصة."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot     = bot
        self.logger  = setup_logger(__name__)
        self.dl      = Downloader(self.logger)
        self.store   = PlaylistStore()
        self.states: dict[int, GuildState] = {}

    # ───────────── أدوات مساعدة ───────────── #
    def _st(self, gid: int) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3600); m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(text: str) -> bool:
        return bool(_RX_URL.match(text or ""))

    # ───────────── اتصال صوتى موثوق ───────────── #
    async def _ensure_voice(self, interaction: discord.Interaction) -> bool:
        st = self._st(interaction.guild_id)

        if st.vc and st.vc.is_connected():
            return True

        channel: discord.VoiceChannel | None = None
        if interaction.user.voice and interaction.user.voice.channel:
            channel = interaction.user.voice.channel
        elif st.vc:
            channel = st.vc.channel      # type: ignore

        if not channel:
            return False

        try:
            st.vc = await channel.connect()
            return True
        except discord.ClientException as e:
            self.logger.warning(f"تعذّر الاتصال بالصوت: {e}")
            return False

    # ───────────── البحث يوتيوب/فيسبوك ───────────── #
    async def _yt_search(self, query: str) -> list[dict]:
        from yt_dlp import YoutubeDL
        opts = {"quiet": True, "extract_flat": False,
                "skip_download": True, "format": "bestaudio/best"}
        try:
            data = await asyncio.to_thread(
                lambda: YoutubeDL(opts).extract_info(
                    f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False))
            res = []
            for e in data.get("entries", []):
                res.append({
                    "url": f"https://www.youtube.com/watch?v={e['id']}",
                    "title": e.get("title", "—"),
                    "duration": self._fmt(e.get("duration", 0)),
                    "thumb": e.get("thumbnail")
                })
            return res
        except Exception as exc:
            self.logger.error(f"[بحث] {exc}", exc_info=True)
            return []

    # ════════════════════════════════
    #        إدارة قوائم التشغيل
    # ════════════════════════════════
    @app_commands.command(name="plist-create", description="إنشاء قائمة تشغيل جديدة")
    async def plist_create(self, interaction: discord.Interaction, name: str):
        try:
            self.store.create(interaction.guild_id, interaction.user.id, name)
            await interaction.response.send_message(f"✅ تم إنشاء **{name}**.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    @app_commands.command(name="plist-list", description="عرض أسماء القوائم المتاحة")
    async def plist_list(self, interaction: discord.Interaction):
        names = self.store.list_names(interaction.guild_id, interaction.user.id)
        if not names:
            return await interaction.response.send_message("لا توجد قوائم.", ephemeral=True)
        await interaction.response.send_message(
            "القوائم: " + ", ".join(f"`{n}`" for n in names), ephemeral=True
        )

    # -------- إضافة مقطع -------- #
    @app_commands.command(name="plist-add", description="إضافة مقطع إلى قائمة")
    async def plist_add(self, interaction: discord.Interaction, name: str, input: str):
        await interaction.response.defer(thinking=True, ephemeral=True)

        async def _insert(url: str):
            try:
                self.store.add_track(interaction.guild_id, interaction.user.id, name, url)
                await interaction.followup.send("✅ أُضيف المقطع.", ephemeral=True)
            except (KeyError, PermissionError, ValueError) as e:
                await interaction.followup.send(str(e), ephemeral=True)

        if self._is_url(input):
            return await _insert(input)

        # بحث وإظهار النتائج لاختيارها
        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا توجد نتائج.", ephemeral=True)

        embeds = []
        for idx, r in enumerate(results, 1):
            e = (discord.Embed(title=r["title"],
                               description=f"المدة: {r['duration']}",
                               color=0x3498db)
                 .set_footer(text=f"نتيجة {idx}/{len(results)}"))
            if r["thumb"]: e.set_thumbnail(url=r["thumb"])
            embeds.append(e)

        class _Sel(discord.ui.Select):
            def __init__(self):
                super().__init__(placeholder="اختر المقطع",
                                 options=[discord.SelectOption(
                                     label=f"{r['title'][:80]} [{r['duration']}]",
                                     value=r["url"]) for r in results])

            async def callback(self, i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await _insert(self.values[0])
                for c in self.view.children: c.disabled = True
                await i.message.edit(view=self.view)
                self.view.stop()

        v = discord.ui.View(); v.add_item(_Sel())
        await interaction.followup.send(embeds=embeds, view=v, ephemeral=True)

    # -------- إزالة مقطع -------- #
    @app_commands.command(name="plist-remove", description="حذف مقطع برقم ترتيبه")
    async def plist_remove(self, interaction: discord.Interaction,
                           name: str, number: int):
        try:
            self.store.remove_track(interaction.guild_id, interaction.user.id, name, number)
            await interaction.response.send_message("🗑️ تم الحذف.", ephemeral=True)
        except (KeyError, PermissionError, IndexError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    # -------- عرض المحتوى -------- #
    @app_commands.command(name="plist-show", description="عرض محتويات قائمة")
    async def plist_show(self, interaction: discord.Interaction, name: str):
        urls = self.store.get_urls(interaction.guild_id, interaction.user.id, name)
        if urls is None:
            return await interaction.response.send_message("❌ القائمة غير موجودة.", ephemeral=True)
        if not urls:
            return await interaction.response.send_message("القائمة فارغة.", ephemeral=True)

        emb = discord.Embed(title=f"قائمة: {name}", color=0x2ecc71)
        for i, u in enumerate(urls, 1):
            emb.add_field(name=str(i), value=u, inline=False)
        await interaction.response.send_message(embed=emb, ephemeral=True)

    # -------- حذف كامل -------- #
    @app_commands.command(name="plist-delete", description="حذف القائمة بالكامل")
    async def plist_delete(self, interaction: discord.Interaction, name: str):
        try:
            self.store.delete(interaction.guild_id, interaction.user.id, name)
            await interaction.response.send_message("🗑️ تم حذف القائمة.", ephemeral=True)
        except (KeyError, PermissionError) as e:
            await interaction.response.send_message(str(e), ephemeral=True)

    # -------- تشغيل القائمة -------- #
    @app_commands.command(name="plist-play", description="تشغيل قائمة محفوظة")
    async def plist_play(self, interaction: discord.Interaction, name: str):
        urls = self.store.get_urls(interaction.guild_id, interaction.user.id, name)
        if urls is None:
            return await interaction.response.send_message("❌ القائمة غير موجودة.", ephemeral=True)
        if not urls:
            return await interaction.response.send_message("القائمة فارغة.", ephemeral=True)

        st = self._st(interaction.guild_id)
        st.playlist = [{"url": u} for u in urls]
        st.index = -1
        await interaction.response.send_message(f"📜 تشغيل قائمة **{name}**.", ephemeral=True)
        if await self._ensure_voice(interaction):
            await self._play_current(interaction)

    # ════════════════════════════════
    #            /stream
    # ════════════════════════════════
    @app_commands.command(name="stream", description="رابط أو كلمات بحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 انضم إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # رابط مباشر
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث بالكلمات (ephemeral)
        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا توجد نتائج.", ephemeral=True)

        embeds = []
        for idx, r in enumerate(results, 1):
            e = discord.Embed(title=r["title"],
                              description=f"المدة: {r['duration']}",
                              color=0x3498db)
            if r["thumb"]: e.set_thumbnail(url=r["thumb"])
            e.set_footer(text=f"نتيجة {idx}/{len(results)}")
            embeds.append(e)

        class _SearchSelect(discord.ui.Select):
            def __init__(self, cog: "Player"):
                super().__init__(placeholder="اختر المقطع",
                                 options=[discord.SelectOption(
                                     label=f"{r['title'][:80]} [{r['duration']}]",
                                     value=r["url"]) for r in results])
                self.cog = cog

            async def callback(self, i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await self.cog._handle_stream(i, self.values[0])
                for c in self.view.children: c.disabled = True
                await i.message.edit(view=self.view)
                self.view.stop()

        v = discord.ui.View(); v.add_item(_SearchSelect(self))
        await interaction.followup.send(embeds=embeds, view=v, ephemeral=True)

    # ════════════════════════════════
    #           أوامر الطابور
    # ════════════════════════════════
    @app_commands.command(name="queue", description="عرض قائمة التشغيل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)

        e = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, itm in enumerate(st.playlist, 1):
            p = "▶️" if i-1 == st.index else "  "
            e.add_field(name=f"{p} {i}.", value=itm["title"], inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @app_commands.command(name="jump", description="الانتقال لمقطع معيّن")
    async def jump(self, interaction: discord.Interaction, number: int):
        st = self._st(interaction.guild_id)
        if not 1 <= number <= len(st.playlist):
            return await interaction.response.send_message("❌ رقم غير صالح.", ephemeral=True)
        st.index = number - 2
        if st.vc: st.vc.stop()
        await interaction.response.send_message(f"⏩ الانتقال إلى {number}.", ephemeral=True)

    @app_commands.command(name="restart", description="العودة للبداية")
    async def restart(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st.index = -1
        if st.vc: st.vc.stop()
        await interaction.response.send_message("⏮️ عدنا إلى البداية.", ephemeral=True)

    @app_commands.command(name="play", description="تشغيل / استئناف")
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

    @app_commands.command(name="skip", description="تخطى الحالى")
    async def skip(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message("🔹 الطابور فارغ.", ephemeral=True)
        st.index = (st.index + 1) % len(st.playlist)
        if st.vc: st.vc.stop()
        await interaction.response.send_message("⏭️ تم التخطي.", ephemeral=True)

    @app_commands.command(name="stop", description="إيقاف ومسح الطابور")
    async def stop(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        st.playlist.clear(); st.index = -1
        if st.vc:
            st.vc.stop(); await st.vc.disconnect(); st.vc = None
        if st.timer: st.timer.cancel()
        await interaction.response.send_message("⏹️ توقّف كل شيء.", ephemeral=True)

    # ════════════════════════════════
    #              تشغيل
    # ════════════════════════════════
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        try:
            res = await self.dl.download(url)
        except Exception:
            return await interaction.followup.send("⚠️ المقطع غير متاح أو محجوب.", ephemeral=True)

        st.playlist.append(res if isinstance(res, dict) else res[0])
        await interaction.followup.send("✅ أُضيف المقطع.", ephemeral=True)
        if await self._ensure_voice(interaction):
            if st.index == -1:
                await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            st.index = -1
            return
        if not await self._ensure_voice(interaction):       # تأكد الاتصال
            return

        st.index = (st.index + 1) % len(st.playlist)
        item = st.playlist[st.index]
        if "path" not in item:
            item.update(await self.dl.download(item["url"]))

        # prefetch الملفين التاليين
        async def _prefetch():
            idx = st.index
            fut = []
            for off in (1, 2):
                nxt = st.playlist[(idx + off) % len(st.playlist)]
                if "url" in nxt and "path" not in nxt:
                    fut.append(self.dl.download(nxt["url"]))
            if fut:
                await asyncio.gather(*fut, return_exceptions=True)

        if st.prefetch_task and not st.prefetch_task.done():
            st.prefetch_task.cancel()
        st.prefetch_task = asyncio.create_task(_prefetch())

        # تشغيل فعلى
        src = discord.FFmpegOpusAudio(item["path"],
                                      executable=self.bot.ffmpeg_exe,
                                      before_options="-nostdin",
                                      options="-vn")
        st.vc.play(src,
                   after=lambda e:
                     self.bot.loop.create_task(self._after(interaction, e)))

        # embed معلومات
        dur = int(MP3(item["path"]).info.length)
        emb = (discord.Embed(title=item["title"], color=0x2ecc71)
               .add_field(name="المدة", value=self._fmt(dur))
               .set_footer(text=f"{st.index+1}/{len(st.playlist)}"))
        if st.msg is None:
            st.msg = await interaction.channel.send(embed=emb)
        else:
            await st.msg.edit(embed=emb)

        if st.timer: st.timer.cancel()
        st.timer = self.bot.loop.create_task(self._ticker(interaction.guild_id))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error("FFmpeg/Playback Error", exc_info=True)
        if await self._ensure_voice(interaction):
            await self._play_current(interaction)

    async def _ticker(self, gid: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st.vc and st.vc.is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            emb = st.msg.embeds[0]
            if len(emb.fields) == 2:
                emb.set_field_at(1, name="المنقضى", value=self._fmt(elapsed))
            else:
                emb.add_field(name="المنقضى", value=self._fmt(elapsed))
            await st.msg.edit(embed=emb)
            await asyncio.sleep(10)


async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
