# modules/playlist_store.py
import json
from pathlib import Path
from typing import Dict, List, Optional

_STORE = Path("playlists.json")


class PlaylistStore:
    """
    • قائمة التشغيل محفوظة داخل السيرفر (guild) الذى أُنشِئت فيه لكل الأعضاء.
    • المالك (owner_id) يرى قوائمه فى أى سيرفر آخر.
    """
    def __init__(self) -> None:
        # guild_id(str) -> { name(str): {"owner": user_id(str), "urls": [str,…]} }
        self._data: Dict[str, Dict[str, Dict[str, object]]] = (
            json.loads(_STORE.read_text(encoding="utf-8"))
            if _STORE.exists() else {}
        )

    # ---------- أدوات داخليّة ---------- #
    def _flush(self) -> None:
        _STORE.write_text(json.dumps(self._data, ensure_ascii=False, indent=2),
                          encoding="utf-8")

    def _get_record(self, guild_id: int, name: str) -> Optional[Dict]:
        return self._data.get(str(guild_id), {}).get(name)

    # ---------- عمليات أساسيّة ---------- #
    def create(self, guild_id: int, owner_id: int, name: str) -> None:
        g = self._data.setdefault(str(guild_id), {})
        if name in g:
            raise ValueError("اسم هذه القائمة مستخدم بالفعل فى هذا السيرفر.")
        g[name] = {"owner": str(owner_id), "urls": []}
        self._flush()

    def add_track(self, guild_id: int, owner_id: int, name: str, url: str) -> None:
        rec = self._get_record(guild_id, name)
        if rec is None:
            raise KeyError("القائمة غير موجودة.")
        if rec["owner"] != str(owner_id) and guild_id != 0:
            raise PermissionError("فقط مالك القائمة يستطيع تعديلها.")
        rec["urls"].append(url)
        self._flush()

    def remove_track(self, guild_id: int, owner_id: int, name: str, index: int) -> None:
        rec = self._get_record(guild_id, name)
        if rec is None:
            raise KeyError("القائمة غير موجودة.")
        if rec["owner"] != str(owner_id):
            raise PermissionError("فقط مالك القائمة يستطيع تعديلها.")
        if not 1 <= index <= len(rec["urls"]):
            raise IndexError("رقم مقطع غير صحيح.")
        rec["urls"].pop(index - 1)
        self._flush()

    def delete(self, guild_id: int, owner_id: int, name: str) -> None:
        g = self._data.get(str(guild_id))
        if not g or name not in g:
            raise KeyError("القائمة غير موجودة.")
        if g[name]["owner"] != str(owner_id):
            raise PermissionError("فقط مالك القائمة يستطيع الحذف.")
        del g[name]
        self._flush()

    # ---------- استرجاع ---------- #
    def list_names(self, guild_id: int, user_id: int) -> List[str]:
        names = set()
        # قوائم السيرفر
        names.update(self._data.get(str(guild_id), {}).keys())
        # قوائم يملكها المستخدم فى أى سيرفر
        for g in self._data.values():
            for n, rec in g.items():
                if rec["owner"] == str(user_id):
                    names.add(n)
        return sorted(names)

    def get_urls(self, guild_id: int, user_id: int, name: str) -> Optional[List[str]]:
        # أولوية: القائمة فى هذا السيرفر – ثم قوائم يملكها المستخدم
        rec = self._get_record(guild_id, name)
        if rec:
            return list(rec["urls"])
        for g in self._data.values():
            if name in g and g[name]["owner"] == str(user_id):
                return list(g[name]["urls"])
        return None
