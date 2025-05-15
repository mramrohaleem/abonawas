import discord, asyncio
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
from collections import deque
from datetime import datetime

class Player(commands.Cog):
    """
    Cog لتنفيذ أوامر السلاش لبث التلاوات من MP3 أو YouTube.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger()
        self.downloader = Downloader(self.logger)
        self.players: dict[int, dict] = {}

    # ---------- حالــة كــل سـيـرفــر ----------
    def get_state(self, gid: int) -> dict:
        return self.players.setdefault(gid, {
            "queue": deque(), "vc": None, "current": None,
            "timer_task": None, "download_task": None, "message": None
        })

    # ---------- أوامــر الســلاش ----------
    @app_commands.command(name="stream", description="أضف رابط MP3 أو YouTube للطابور وابدأ التشغيل")
    @app_commands.describe(url="رابط مباشر MP3 أو فيديو YouTube/ساوندكلاود")
    async def stream(self, interaction: discord.Interaction, url: str):
        await self._handle_stream(interaction, url)

    @app_commands.command(name="yt", description="اختصار لإضافة رابط YouTube ثم التشغيل")
    @app_commands.describe(url="رابط فيديو YouTube")
    async def yt(self, interaction: discord.Interaction, url: str):
        await self._handle_stream(interaction, url)

    # أمر /play /pause /skip /stop /help تبقى كما هي (الكود السابق) -----------------
    # --- فقط عرضنا الأجزاء المعدّلة أدناه لتقليل المساحة ---

    # ---------- المساعد الداخلي المشترك لأوامر stream / yt ----------
    async def _handle_stream(self, interaction: discord.Interaction, url: str):
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("🚫 يجب أن تكون في قناة صوتية.", ephemeral=True)

        await interaction.response.defer(thinking=True)
        st = self.get_state(interaction.guild_id)
        st["queue"].append(url)
        self.logger.info(f"[{interaction.guild_id}] Added to queue: {url}")

        if not st["vc"] or not st["vc"].is_connected():
            st["vc"] = await interaction.user.voice.channel.connect()
            self.logger.info(f"[{interaction.guild_id}] Voice connected")

        if not st["current"]:
            await self._play_next(interaction, is_initial=True)
        else:
            await interaction.followup.send(f"➕ تمت الإضافة إلى الطابور (الموقع: {len(st['queue'])})", ephemeral=True)

    # ---------- بقية الدوال play/pause/skip/stop/help + المنطق الداخلي (_play_next, _after_play …) تبقى كما في نسختك الأخيرة ----------
    # لم تتغير، لذا يمكنك إبقاء ما سبق بدون تعديل.

    #  ضع هنا الدوال slash_play و slash_pause و slash_skip و slash_stop و slash_help
    #  وأيضًا _play_next/_after_play/_update_timer/_format_time بنفس ما أرسلته سابقًا.

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
