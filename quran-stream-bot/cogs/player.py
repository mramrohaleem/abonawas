# cogs/player.py

import discord
from discord import app_commands
from discord.ext import commands
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from mutagen.mp3 import MP3
import asyncio
from collections import deque
from datetime import datetime

class Player(commands.Cog):
    """
    Cog implementing slash commands for audio streaming.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = setup_logger()
        self.downloader = Downloader(self.logger)
        # per-guild playback state
        self.players: dict[int, dict] = {}

    def get_state(self, guild_id: int) -> dict:
        return self.players.setdefault(guild_id, {
            "queue": deque(),
            "vc": None,
            "current": None,
            "timer_task": None,
            "download_task": None,
            "message": None
        })

    @app_commands.command(
        name="stream",
        description="أضف رابط MP3 إلى الطابور وابدأ التشغيل"
    )
    @app_commands.describe(url="رابط مباشر لملف MP3")
    async def slash_stream(self, interaction: discord.Interaction, url: str):
        # ... (باقي الكود كما كان)

    @app_commands.command(
        name="play",
        description="تشغيل أو استئناف المسار الحالي من الطابور"
    )
    async def slash_play(self, interaction: discord.Interaction):
        st = self.get_state(interaction.guild_id)
        vc = st["vc"]

        # إذا كان موقوف مؤقتًا
        if vc and vc.is_paused():
            vc.resume()
            self.logger.info(f"[{interaction.guild_id}] Resumed via /play")
            return await interaction.response.send_message(
                "▶️ استُؤنف التشغيل", ephemeral=True
            )

        # إذا لا شيء يُشغّل حاليًا ولكن هناك طابور
        if (not vc or not vc.is_playing()) and st["queue"]:
            await interaction.response.defer(thinking=True)
            await self._play_next(interaction, is_initial=False)
            return

        # خلاف ذلك
        await interaction.response.send_message(
            "لا يوجد شيء مُوقوف أو في الطابور ليتم تشغيله.", ephemeral=True
        )

    @app_commands.command(
        name="pause",
        description="إيقاف المسار الجاري مؤقتًا"
    )
    async def slash_pause(self, interaction: discord.Interaction):
        # ... (باقي الكود كما كان)

    @app_commands.command(
        name="skip",
        description="تخطي إلى المسار التالي"
    )
    async def slash_skip(self, interaction: discord.Interaction):
        # ... (باقي الكود كما كان)

    @app_commands.command(
        name="stop",
        description="إيقاف التشغيل ومسح الطابور"
    )
    async def slash_stop(self, interaction: discord.Interaction):
        # ... (باقي الكود كما كان)

    @app_commands.command(
        name="help",
        description="عرض قائمة الأوامر المتاحة"
    )
    async def slash_help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 دليل استخدام البوت",
            color=discord.Color.green()
        )
        cmds = {
            "/stream [url]": "أضف رابط MP3 إلى الطابور وابدأ التشغيل",
            "/play": "تشغيل أو استئناف المسار الحالي من الطابور",
            "/pause": "إيقاف المسار الجاري مؤقتًا",
            "/skip": "تخطي إلى المسار التالي",
            "/stop": "إيقاف التشغيل ومسح الطابور",
            "/help": "عرض قائمة الأوامر المتاحة"
        }
        for name, desc in cmds.items():
            embed.add_field(name=name, value=desc, inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # … هنا باقي التعاريف الداخلية _play_next, _after_play, _update_timer, _format_time كما كانت

async def setup(bot: commands.Bot):
    await bot.add_cog(Player(bot))
