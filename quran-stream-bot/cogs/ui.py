import discord
from discord import ui, ButtonStyle
from discord.ui import Button, View
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cogs.player import Player

class PlayerControls(View):
    """
    A persistent View containing playback control buttons.
    """
    def __init__(self, player: "Player"):
        super().__init__(timeout=None)  # timeout=None -> persistent
        self.player = player

    @ui.button(emoji="▶️", style=ButtonStyle.green, custom_id="qbot_play")
    async def play(self, button: Button, interaction: discord.Interaction):
        await self.player.resume(interaction)

    @ui.button(emoji="⏸️", style=ButtonStyle.blurple, custom_id="qbot_pause")
    async def pause(self, button: Button, interaction: discord.Interaction):
        await self.player.pause(interaction)

    @ui.button(emoji="⏭️", style=ButtonStyle.gray, custom_id="qbot_next")
    async def skip(self, button: Button, interaction: discord.Interaction):
        await self.player.skip(interaction)

    @ui.button(emoji="⏹️", style=ButtonStyle.red, custom_id="qbot_stop")
    async def stop(self, button: Button, interaction: discord.Interaction):
        await self.player.stop(interaction)
