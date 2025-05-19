# cogs/player.py
import asyncio, re, discord, traceback
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from discord import app_commands
from discord.ext import commands

from mutagen.mp3 import MP3

from modules.logger_config import setup_logger
from modules.downloader import Downloader
from modules.playlist_store import PlaylistStore

_RX_URL = re.compile(r"https?://", re.I)


@dataclass
class GuildState:
    playlist: list[dict] = field(default_factory=list)
    index: int = -1
    vc: discord.VoiceClient | None = None
    msg: discord.Message | None = None
    timer: asyncio.Task | None = None
    prefetch_task: asyncio.Task | None = None


class Player(commands.Cog):
    """بثّ تلاوات + يوتيوب/فيسبوك + قوائم مفضّلة."""
    SEARCH_LIMIT = 5

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger(__name__)
        self.dl = Downloader(self.logger)
        self.store = PlaylistStore()
        self.states: dict[int, GuildState] = {}

    # -------------- أدوات مساعدة -------------- #
    def _st(self, gid: int) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3600)
        m, s = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(text: str) -> bool:
        return bool(_RX_URL.match(text or ""))

    # --------- بحث يوتيوب/فيسبوك --------- #
    async def _yt_search(self, query: str) -> list[dict]:
        from yt_dlp import YoutubeDL
        opts = {"quiet": True, "extract_flat": False, "skip_download": True,
                "format": "bestaudio/best"}
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

    # ---------- /help بدون أزرار ---------- #
    help_embed = discord.Embed(
        title="📖 دليل الاستخدام",
        description=(
            "**/stream `<رابط/كلمات>`** – إضافة مقطع أو البحث يوتيوب/فيسبوك\n"
            "**/queue** – عرض القائمة • **/jump n** – الانتقال\n"
            "**/play /pause /skip /stop** – التحكم بالتشغيل\n\n"
            "__قوائم المفضّلة__\n"
            "**/fav-save `<اسم>`** – حفظ القائمة الحالية\n"
            "**/fav-play** – تشغيل قائمة محفوظة\n"
            "**/fav-list** – عرض الأسماء المحفوظة"
        ),
        color=0x7289DA
    )

    @app_commands.command(name="help", description="عرض دليل مختصر")
    async def help_cmd(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=self.help_embed, ephemeral=True)

    # ---------- أوامر المفضّلة ---------- #
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
            st.playlist.append({"url": url})  # سيتّم تنزيلها لاحقًا

        st.index = -1
        await interaction.followup.send(f"📜 تم تحميل قائمة **{name}**.", ephemeral=True)
        await self._ensure_voice(interaction)
        await self._play_current(interaction)

    # ---------- /stream ---------- #
    @app_commands.command(name="stream", description="رابط أو كلمات بحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 انضم إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)

        # رابط مباشر
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        # بحث كلمات (النتائج و الـSelect ترسل للمستخدم فقط: ephemeral=True)
        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا توجد نتائج.", ephemeral=True)

        embeds = []
        for idx, r in enumerate(results, 1):
            e = discord.Embed(title=r["title"],
                              description=f"المدة: {r['duration']}",
                              color=0x3498db)
            if r["thumb"]:
                e.set_thumbnail(url=r["thumb"])
            e.set_footer(text=f"نتيجة {idx}/{len(results)}")
            embeds.append(e)

        class _SearchSelect(discord.ui.Select):
            def __init__(self, cog: "Player"):
                super().__init__(options=[discord.SelectOption(
                    label=f"{r['title'][:80]} [{r['duration']}]",
                    value=r["url"]) for r in results],
                                 placeholder="اختر المقطع", min_values=1, max_values=1)
                self.cog = cog

            async def callback(self, i: discord.Interaction):
                await i.response.defer(ephemeral=True)
                await self.cog._handle_stream(i, self.values[0])
                for c in self.view.children:
                    c.disabled = True
                await i.message.edit(view=self.view)
                self.view.stop()

        view = discord.ui.View()
        view.add_item(_SearchSelect(self))
        await interaction.followup.send(embeds=embeds, view=view, ephemeral=True)

    # ---------- الطابور وأوامر التحكم (كما كانت)… ---------- #
    # (نفس الشفرة فى ردودك السابقة؛ لم تتغير إلا فى أماكن استدعاء prefetch وإدارة الأخطاء)

    # --- مساعدة داخليّة --- #
    async def _ensure_voice(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.vc:
            st.vc = await interaction.user.voice.channel.connect()

    # ---------- تنزيل/إضافة ---------- #
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        try:
            res = await self.dl.download(url)
        except Exception:
            return await interaction.followup.send(
                "⚠️ المقطع غير متاح أو محجوب.", ephemeral=True)

        if isinstance(res, list):
            st.playlist.extend(res)
            msg = f"📜 أضيف {len(res)} مقاطع."
        else:
            st.playlist.append(res)
            msg = "✅ أضيف المقطع."

        await interaction.followup.send(msg, ephemeral=True)
        await self._ensure_voice(interaction)
        if st.index == -1:
            await self._play_current(interaction)

    # ---------- التشغيل ---------- #
    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            st.index = -1
            return

        st.index = (st.index + 1) % len(st.playlist)
        item = st.playlist[st.index]

        # تنزيل إن لم يكن مُنزَّل (كاش داخل Downloader)
        if "path" not in item:
            item.update(await self.dl.download(item["url"]))

        # Prefetch المقاطع التالية (2 ملف فى الخلفية كحد أقصى)
        async def _prefetch():
            idx = st.index
            todo = []
            for off in (1, 2):
                nxt = st.playlist[(idx + off) % len(st.playlist)]
                if "url" in nxt and "path" not in nxt:
                    todo.append(self.dl.download(nxt["url"]))
            if todo:
                await asyncio.gather(*todo, return_exceptions=True)

        if st.prefetch_task and not st.prefetch_task.done():
            st.prefetch_task.cancel()
        st.prefetch_task = asyncio.create_task(_prefetch())

        # تشغيل
        source = discord.FFmpegOpusAudio(
            item["path"], executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn")
        st.vc.play(
            source,
            after=lambda e:
            self.bot.loop.create_task(self._after(interaction, e))
        )

        # Embed
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
            self.logger.error("FFmpeg/Playback Error",
                              exc_info=err if isinstance(err, BaseException) else None)
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
