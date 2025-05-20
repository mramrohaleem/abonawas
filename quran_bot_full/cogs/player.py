
# shortened for brevity, identical to earlier provided stable version with _ensure_voice etc.
import asyncio, re, discord
from dataclasses import dataclass, field
from datetime import datetime
from discord import app_commands
from discord.ext import commands
from mutagen.mp3 import MP3
from modules.logger_config import setup_logger
from modules.downloader import Downloader
from modules.playlist_store import PlaylistStore

_RX_URL = re.compile(r"https?://", re.I)

@dataclass
class GuildState:
    playlist: list[dict] = field(default_factory=list)
    index:int = -1
    vc: discord.VoiceClient|None = None
    msg: discord.Message|None = None
    timer: asyncio.Task|None = None
    prefetch_task: asyncio.Task|None = None

class Player(commands.Cog):
    SEARCH_LIMIT = 5
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        self.log = setup_logger(__name__)
        self.dl  = Downloader(self.log)
        self.store = PlaylistStore()
        self.states:dict[int,GuildState] = {}

    # helpers
    def _st(self, gid:int)->GuildState:
        return self.states.setdefault(gid, GuildState())

    @staticmethod
    def _fmt(sec:int)->str:
        h,rem = divmod(int(sec),3600); m,s=divmod(rem,60)
        return f"{h:02}:{m:02}:{s:02}"

    @staticmethod
    def _is_url(t:str)->bool:
        return bool(_RX_URL.match(t or ""))

    async def _ensure_voice(self, interaction:discord.Interaction)->bool:
        st = self._st(interaction.guild_id)
        if st.vc and st.vc.is_connected():
            return True
        if interaction.user.voice and interaction.user.voice.channel:
            try:
                st.vc = await interaction.user.voice.channel.connect()
                return True
            except discord.ClientException as e:
                self.log.warning(f"صوت: {e}")
        return False

    # search YT
    async def _yt_search(self, query:str):
        from yt_dlp import YoutubeDL
        opts = {"quiet":True,"extract_flat":False,"skip_download":True,"format":"bestaudio/best"}
        try:
            data = await asyncio.to_thread(lambda: YoutubeDL(opts).extract_info(f"ytsearch{self.SEARCH_LIMIT}:{query}",download=False))
            out=[]
            for e in data.get("entries",[]):
                out.append({"url":f"https://www.youtube.com/watch?v={e['id']}","title":e.get("title","—"),"duration":self._fmt(e.get("duration",0)),"thumb":e.get("thumbnail")})
            return out
        except Exception as exc:
            self.log.error(f"YT search {exc}")
            return []

    # fav playlist commands (unchanged)...

    # stream, queue, etc. omitted for brevity — assume same as earlier stable code
