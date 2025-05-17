# cogs/player.py
import asyncio, re, discord
from discord import app_commands
from discord.ext import commands
from mutagen.mp3 import MP3
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional
from yt_dlp import DownloadError
from modules.downloader import Downloader
from modules.logger_config import setup_logger

# ---------- حالة الجيلد ---------- #
@dataclass
class GuildState:
    playlist: List[dict] = field(default_factory=list)
    index: int = -1
    vc: Optional[discord.VoiceClient] = None
    msg: Optional[discord.Message] = None
    timer: Optional[asyncio.Task] = None

# ---------- الكوج ---------- #
class Player(commands.Cog):
    SEARCH_LIMIT = 5
    PREFETCH     = 3              # عدد المقاطع المُحمّلة مسبقًا
    MAX_PREFETCH = 2              # أقصى مهام متزامنة

    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger(__name__)
        self.dl     = Downloader(self.logger)
        self.states: dict[int, GuildState] = {}

    # ---------- أدوات ---------- #
    def _st(self, gid: int) -> GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec: int) -> str:
        h, rem = divmod(int(sec), 3_600)
        m, s   = divmod(rem, 60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(t: str) -> bool:
        return bool(re.match(r"https?://", t or ""))

    # ---------- البحث ---------- #
    async def _yt_search(self, query: str) -> List[dict]:
        from yt_dlp import YoutubeDL
        opts = {"quiet": True, "extract_flat": False,
                "skip_download": True, "format": "bestaudio"}
        def run():
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"ytsearch{self.SEARCH_LIMIT}:{query}", download=False)
            return info
        data = await asyncio.to_thread(run)
        out = []
        for e in data.get("entries", []):
            out.append({
                "url": f"https://youtu.be/{e['id']}",
                "title": e.get("title", "—"),
                "duration": self._fmt(e.get("duration", 0)),
                "thumb": e.get("thumbnail")
            })
        return out

    # ---------- View ---------- #
    class _Select(discord.ui.Select):
        def __init__(self, results, cog: "Player"):
            self.cog = cog
            opts = [discord.SelectOption(
                        label=f"{r['title'][:80]} [{r['duration']}]",
                        value=r["url"]) for r in results]
            super().__init__(placeholder="اختر المقطع", options=opts)

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            await self.cog._handle_stream(interaction, self.values[0])
            for c in self.view.children:
                c.disabled = True
            await interaction.message.edit(view=self.view)
            self.view.stop()

    class _View(discord.ui.View):
        def __init__(self, results, cog):
            super().__init__(timeout=60)
            self.add_item(Player._Select(results, cog))

    # ---------- /stream ---------- #
    @app_commands.command(name="stream",
        description="رابط (YouTube/MP3) أو كلمات للبحث")
    async def stream(self, interaction: discord.Interaction, input: str):
        if not (interaction.user.voice and interaction.user.voice.channel):
            return await interaction.response.send_message(
                "🚫 انضمّ إلى قناة صوتية أولًا.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        if self._is_url(input):
            return await self._handle_stream(interaction, input)

        results = await self._yt_search(input)
        if not results:
            return await interaction.followup.send("❌ لا نتائج.", ephemeral=True)

        embeds = []
        for i, r in enumerate(results, 1):
            e = discord.Embed(title=r["title"],
                              description=f"المدة: {r['duration']}",
                              color=0x3498db)
            if r["thumb"]:
                e.set_thumbnail(url=r["thumb"])
            e.set_footer(text=f"{i}/{len(results)}")
            embeds.append(e)

        await interaction.followup.send(embeds=embeds,
                                        view=self._View(results, self),
                                        ephemeral=True)

    # ---------- أوامر الطابور (كما كانت)… ---------- #
    # ... (لا تغيير جوهري على الأوامر التالية غير استبدال st["field"] بـ st.field) ...

    @app_commands.command(name="queue", description="عرض قائمة التشغيل")
    async def queue(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:
            return await interaction.response.send_message(
                "🔹 الطابور فارغ.", ephemeral=True)

        embed = discord.Embed(title="قائمة التشغيل", color=0x2ecc71)
        for i, itm in enumerate(st.playlist, 1):
            prefix = "▶️" if i-1 == st.index else "  "
            embed.add_field(name=f"{prefix} {i}.", value=itm["title"],
                            inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # ... jump / restart / play / pause / skip / stop (نفس المنطق مع dataclass) ...

    # ---------- التنزيل والتشغيل ---------- #
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        st = self._st(interaction.guild_id)
        try:
            res = await self.dl.download(url)
        except DownloadError:
            return await interaction.followup.send(
                "❌ المقطع غير متاح أو محجوب.", ephemeral=True)

        if isinstance(res, list):
            st.playlist.extend(res)
            msg = f"📜 أُضيف {len(res)} مقاطع."
        else:
            st.playlist.append(res)
            msg = "✅ أُضيف المقطع."
        await interaction.followup.send(msg, ephemeral=True)

        if not st.vc:
            st.vc = await interaction.user.voice.channel.connect()
        if st.index == -1:
            await self._play_current(interaction)

    async def _play_current(self, interaction: discord.Interaction):
        st = self._st(interaction.guild_id)
        if not st.playlist:      # حماية من قسمة صفر
            st.index = -1
            return

        st.index = (st.index + 1) % len(st.playlist)
        itm = st.playlist[st.index]

        if "path" not in itm:
            itm.update(await self.dl.download(itm["url"]))

        # Prefetch
        sem = asyncio.Semaphore(self.MAX_PREFETCH)
        async def _pf(u):
            async with sem:
                try:
                    await self.dl.download(u)
                except Exception:
                    pass
        nxt = [p["url"] for p in st.playlist[st.index+1:st.index+1+self.PREFETCH]
               if "url" in p and "path" not in p]
        asyncio.create_task(asyncio.gather(*(_pf(u) for u in nxt)))

        # التشغيل الفعلي
        src = discord.FFmpegOpusAudio(
            itm["path"], executable=self.bot.ffmpeg_exe,
            before_options="-nostdin", options="-vn"
        )
        st.vc.play(src, after=lambda e:
                   self.bot.loop.create_task(self._after(interaction, e)))

        # Embed
        dur = int(MP3(itm["path"]).info.length)
        embed = discord.Embed(title=itm["title"], color=0x2ecc71)
        embed.add_field(name="المدة", value=self._fmt(dur))
        embed.set_footer(text=f"{st.index+1}/{len(st.playlist)}")

        if st.msg is None:
            st.msg = await interaction.channel.send(embed=embed)
        else:
            await st.msg.edit(embed=embed)

        # مؤقّت التقدم
        if st.timer: st.timer.cancel()
        st.timer = self.bot.loop.create_task(self._ticker(
            interaction.guild_id, dur))

    async def _after(self, interaction: discord.Interaction, err):
        if err:
            self.logger.error(f"Playback error: {err}", exc_info=True)
        await self._play_current(interaction)

    async def _ticker(self, gid: int, total: int):
        st = self._st(gid)
        start = datetime.utcnow()
        while st.vc and st.vc.is_playing():
            elapsed = int((datetime.utcnow() - start).total_seconds())
            embed = st.msg.embeds[0]
            if len(embed.fields) == 2:
                embed.set_field_at(1, name="المنقضي",
                                   value=self._fmt(elapsed))
            else:
                embed.add_field(name="المنقضي",
                                value=self._fmt(elapsed))
            await st.msg.edit(embed=embed)
            await asyncio.sleep(10)

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
