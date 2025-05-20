import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View
from discord import ButtonStyle
from cogs.ui import PlayerControls

class MainMenuView(View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🔍 Stream", style=ButtonStyle.primary, custom_id="main_stream")
    async def stream(self, button: discord.ui.Button, interaction: discord.Interaction):
        await interaction.response.send_modal(StreamModal(self.bot))

    @discord.ui.button(label="📜 Queue", style=ButtonStyle.secondary, custom_id="main_queue")
    async def queue(self, button: discord.ui.Button, interaction: discord.Interaction):
        await self.bot.get_cog("Player").queue(interaction)

    @discord.ui.button(label="▶️ Controls", style=ButtonStyle.success, custom_id="main_controls")
    async def controls(self, button: discord.ui.Button, interaction: discord.Interaction):
        player = self.bot.get_cog("Player")
        view = PlayerControls(player)
        await interaction.response.send_message("🎛️ Playback Controls:", view=view, ephemeral=True)

class StreamModal(discord.ui.Modal, title="Stream Quran"):
    input = discord.ui.TextInput(label="الرابط أو كلمات البحث", placeholder="أدخل رابط يوتيوب أو كلمات البحث", style=discord.TextStyle.short)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await self.bot.get_cog("Player").stream(interaction, self.input.value)

class Menu(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="menu", description="افتح القائمة الرئيسية")
    async def menu(self, interaction: discord.Interaction):
        await interaction.response.send_message("اختر خيارًا من القائمة:", view=MainMenuView(self.bot), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Menu(bot))
