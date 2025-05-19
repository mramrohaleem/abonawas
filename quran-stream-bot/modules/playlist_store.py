import json
from json import JSONDecodeError
from pathlib import Path
from typing import Dict, List

_STORE_PATH = Path("favorite_playlists.json")


class PlaylistStore:
    """تخزين قوائم التشغيل المفضَّلة فى ملف JSON بسيط."""
    def __init__(self) -> None:
        # guild_id(str) -> {name: [urls]}
        self._data: Dict[str, Dict[str, List[str]]]

        if _STORE_PATH.exists():
            try:
                self._data = json.loads(_STORE_PATH.read_text(encoding="utf-8"))
            except JSONDecodeError:
                # الملف فارغ أو معطوب → ابدأ من الصفر ولا تَخرُج
                self._data = {}
        else:
            self._data = {}

    # ---------- واجهة عامّة ---------- #
    def save(self, guild_id: int, name: str, urls: List[str]) -> None:
        gkey = str(guild_id)
        self._data.setdefault(gkey, {})[name] = urls
        self._flush()

    def list_names(self, guild_id: int) -> List[str]:
        return list(self._data.get(str(guild_id), {}).keys())

    def get(self, guild_id: int, name: str) -> List[str] | None:
        return self._data.get(str(guild_id), {}).get(name)

    # ---------- داخلى ---------- #
    def _flush(self) -> None:
        _STORE_PATH.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
