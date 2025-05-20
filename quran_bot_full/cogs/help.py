
import discord, textwrap
from discord.ext import commands
from discord import app_commands

HELP_TEXT = textwrap.dedent("""
    **/stream** إضافة مقطع أو بحث
    **/queue /jump /restart** إدارة الطابور
    **/fav-save /fav-list /fav-play** القوائم المفضّلة
    **/azkar enable|disable | set-cooldown** الأذكار العشوائية
""")

class HelpCog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="عرض المساعدة")
    async def help_cmd(self, interaction:discord.Interaction):
        embed = discord.Embed(title="دليل الأوامر", description=HELP_TEXT, color=0x7289DA)
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot):
    await bot.add_cog(HelpCog(bot))
