
import json
from pathlib import Path
from typing import Dict, List

_STORE = Path("favorite_playlists.json")

class PlaylistStore:
    def __init__(self):
        if _STORE.exists():
            self._data: Dict[str, Dict[str, List[str]]] = json.loads(_STORE.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def list_names(self, gid:int) -> List[str]:
        return list(self._data.get(str(gid), {}).keys())

    def save(self, gid:int, name:str, urls:List[str]):
        self._data.setdefault(str(gid), {})[name] = urls
        self._flush()

    def get(self, gid:int, name:str):
        return self._data.get(str(gid), {}).get(name)

    def _flush(self):
        _STORE.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
