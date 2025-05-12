import asyncio
import yt_dlp
from discord import FFmpegPCMAudio
from discord.ext import commands
from discord import VoiceChannel, VoiceClient

class AudioService:
    def __init__(self):
        self._player = None
        self._voice: VoiceClient | None = None
        self._loop = asyncio.get_event_loop()

    async def play_url(self, channel: VoiceChannel, url: str):
        '''Join channel, stream audio via yt-dlp and FFmpeg.'''
        if self._voice and self._voice.is_connected():
            await self._voice.disconnect()
        self._voice = await channel.connect()
        ydl_opts = {'format': 'bestaudio', 'quiet': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            audio_url = info['url']
        source = FFmpegPCMAudio(audio_url)
        self._voice.play(source)

    async def stop(self):
        '''Stop playback and disconnect.'''
        if self._voice:
            await self._voice.disconnect()
            self._voice = None
