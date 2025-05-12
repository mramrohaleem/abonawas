import pytest
from services.audio_service import AudioService
from discord import VoiceChannel

class DummyChannel:
    async def connect(self):
        class DummyVoice:
            def __init__(self): self.played = False
            def play(self, source): self.played = True
            def is_connected(self): return True
            async def disconnect(self): pass
        return DummyVoice()

@pytest.mark.asyncio
async def test_play_url(monkeypatch):
    svc = AudioService()
    channel = DummyChannel()
    await svc.play_url(channel, 'https://www.youtube.com/watch?v=dQw4w9WgXcQ')
    assert svc._voice.played
