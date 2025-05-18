# cogs/help.py
import textwrap

import discord
from discord.ext import commands
from discord import app_commands

HELP_PAGES = [
    {
        "title": "الأوامر الأساسية",
        "text": textwrap.dedent("""
            **/stream <رابط أو كلمات>** – إضافة مقطع أو البحث في يوتيوب/فيسبوك  
            **/play – /pause – /skip – /stop** – التحكم في التشغيل  
            **/queue – /jump – /restart** – إدارة الطابور
        """),
    },
    {
        "title": "نصائح متقدّمة",
        "text": textwrap.dedent("""
            • يدعم روابط: YouTube, Facebook, SoundCloud, …  
            • البوت يحمّل مسبقًا المقطع التالي لضمان تشغيل بلا انقطاع  
            • حدّد **/volume** (إن أضفته) للتحكم في مستوى الصوت
        """),
    },
]


class HelpButton(discord.ui.Button):
    def __init__(self, *, delta: int, **kwargs):
        super().__init__(style=discord.ButtonStyle.primary, **kwargs)
        self.delta = delta

    async def callback(self, interaction: discord.Interaction):
        view: "HelpView" = self.view  # type: ignore
        view.page += self.delta
        view.update()
        await view.show(interaction)


class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.page: int = 0
        self.message: discord.Message | None = None
        self.update()

    # تحديث الأزرار حسب الصفحة
    def update(self):
        self.clear_items()
        self.add_item(
            HelpButton(label="السابق", delta=-1, disabled=self.page == 0)
        )
        self.add_item(
            HelpButton(label="التالي", delta=+1, disabled=self.page == len(HELP_PAGES) - 1)
        )

    async def show(self, interaction: discord.Interaction):
        data = HELP_PAGES[self.page]
        embed = discord.Embed(
            title=data["title"], description=data["text"], color=0x7289DA
        )
        if self.message:
            await self.message.edit(embed=embed, view=self)
        else:
            self.message = await interaction.response.send_message(
                embed=embed, view=self, ephemeral=True
            )


class HelpCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="دليل استخدام البوت")
    async def help_cmd(self, interaction: discord.Interaction):
        view = HelpView()
        await view.show(interaction)


async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCog(bot))
