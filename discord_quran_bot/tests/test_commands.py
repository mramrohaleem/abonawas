import pytest
from discord.ext import commands

@pytest.fixture
def bot():
    return commands.Bot(command_prefix='!')

def test_play_cmd_signature(bot):
    cmd = bot.get_command('play')
    assert cmd and cmd.name == 'play'
