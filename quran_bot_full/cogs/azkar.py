
import asyncio, random, discord
from discord import app_commands
from discord.ext import commands, tasks
from services.azkar_provider import get_random_zekr
from stores.guild_config_store import GuildConfigStore
from modules.logger_config import setup_logger

class AzkarCog(commands.Cog):
    """إرسال أذكار عشوائية فى الشات كل فترة"""
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        self.log = setup_logger(__name__)
        self.store = GuildConfigStore()
        self._task.start()

    def cog_unload(self):
        self._task.cancel()

    # --- الإعداد --- #
    @app_commands.command(name="azkar", description="التحكم فى الأذكار العشوائية")
    async def azkar(self, interaction:discord.Interaction, action:str, value:int|None=None):
        action = action.lower()
        cfg = self.store.get(interaction.guild_id)
        if action in ("enable","on"):
            self.store.update(interaction.guild_id, azkar_enabled=True)
            await interaction.response.send_message("✅ تم تفعيل الأذكار.", ephemeral=True)
        elif action in ("disable","off"):
            self.store.update(interaction.guild_id, azkar_enabled=False)
            await interaction.response.send_message("❎ تم إيقاف الأذكار.", ephemeral=True)
        elif action in ("set-cooldown", "cooldown") and value is not None:
            minutes = max(1, value)
            self.store.update(interaction.guild_id, azkar_cooldown=minutes)
            await interaction.response.send_message(f"⏱️ تم ضبط الفاصل إلى {minutes} دقائق.", ephemeral=True)
        else:
            await interaction.response.send_message("❓ استخدام: enable/disable/set-cooldown <ثواني>", ephemeral=True)

    # --- المهمة الدورية --- #
    @tasks.loop(seconds=60)
    async def _task(self):
        for gid in list(self.store._data.keys()):
            cfg = self.store.get(int(gid))
            if not cfg.get("azkar_enabled"):
                continue
            # rate limit using monotonic dict
        # we'll store last_sent times in attribute
        if not hasattr(self,"_last"):
            self._last={}
        import time
        now=time.time()
        for guild in self.bot.guilds:
            cfg=self.store.get(guild.id)
            if not cfg.get("azkar_enabled"):
                continue
            cd=cfg.get("azkar_cooldown",3600)
            last=self._last.get(guild.id,0)
            if now-last<cd:
                continue
            channel=None
            # pick first text channel bot can send
            for ch in guild.text_channels:
                if ch.permissions_for(guild.me).send_messages:
                    channel=ch; break
            if channel:
                try:
                    zekr=get_random_zekr()
                    await channel.send(f"☘️ **ذكر اليوم:**\n> {zekr}")
                    self._last[guild.id]=now
                except Exception as e:
                    self.log.warning(f"Azkar send: {e}")
    @_task.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(AzkarCog(bot))