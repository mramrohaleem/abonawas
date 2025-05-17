import discord, asyncio
from discord import app_commands
from discord.ext import commands
from yt_dlp import YoutubeDL
from modules.logger_config import setup_logger

SEARCH_LIMIT = 5

class SearchView(discord.ui.View):
    def __init__(self, results, player_cog):
        super().__init__(timeout=60)
        self.player = player_cog
        options = [
            discord.SelectOption(label=r["title"][:100], value=r["url"])
            for r in results
        ]
        self.add_item(discord.ui.Select(placeholder="اختر مقطعًا", options=options))

    @discord.ui.select()
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        url = select.values[0]
        await self.player.stream_callback(interaction, url)
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        self.stop()

class Search(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot    = bot
        self.logger = setup_logger()

    @app_commands.command(name="search", description="ابحث في YouTube وأضف مقطعًا")
    @app_commands.describe(query="كلمة البحث")
    async def search(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        results = await asyncio.to_thread(self._yt_search, query)
        if not results:
            return await interaction.followup.send("لا توجد نتائج.", ephemeral=True)

        # احصل على Player cog
        player = self.bot.get_cog("Player")
        view   = SearchView(results, player)

        embed = discord.Embed(
            title="نتائج البحث",
            description="اختر من القائمة المنسدلة:",
            color=0x95a5a6
        )
        for idx, r in enumerate(results, 1):
            embed.add_field(name=f"{idx}. {r['title']}", value=r["url"], inline=False)

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    def _yt_search(self, query: str):
        opts = {"quiet": True, "extract_flat": "in_playlist", "skip_download": True}
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch{SEARCH_LIMIT}:{query}", download=False)
            return [{"url": entry["url"], "title": entry["title"]} for entry in info["entries"]]

async def setup(bot: commands.Bot):
    await bot.add_cog(Search(bot))
