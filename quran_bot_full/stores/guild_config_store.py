
import json
from pathlib import Path

_CFG = Path("guild_config.json")
_DEFAULT = {
    "owner_id": None,
    "azkar_enabled": False,
    "azkar_cooldown": 3600,   # ثابِت
}

class GuildConfigStore:
    def __init__(self):
        if _CFG.exists():
            self._data = json.loads(_CFG.read_text(encoding="utf-8"))
        else:
            self._data = {}

    def get(self, gid:int):
        return self._data.get(str(gid), _DEFAULT.copy())

    def update(self, gid:int, **kw):
        cfg = self.get(gid)
        cfg.update(kw)
        self._data[str(gid)] = cfg
        self._flush()

    def _flush(self):
        _CFG.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
