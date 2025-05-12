import os
import discord
from discord.ext import commands
from services.audio_service import AudioService

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)
audio = AudioService()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

@bot.command(name='play')
async def play(ctx, url: str):
    '''Stream audio from URL'''
    try:
        channel = ctx.author.voice.channel
        await audio.play_url(channel, url)
        await ctx.send(f'Playing audio from {url}')
    except Exception as e:
        await ctx.send(f'Error: {e}')

@bot.command(name='stop')
async def stop(ctx):
    '''Stop audio and disconnect'''
    try:
        await audio.stop()
        await ctx.send('Stopped and disconnected')
    except Exception as e:
        await ctx.send(f'Error: {e}')

if __name__ == '__main__':
    token = os.getenv('DISCORD_TOKEN')
    bot.run(token)
