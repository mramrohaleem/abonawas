
import random, json, pathlib

_ZEKR_FILE = pathlib.Path("azkar.json")
if _ZEKR_FILE.exists():
    _LIST = json.loads(_ZEKR_FILE.read_text(encoding="utf-8"))
else:
    _LIST = ["سبحان الله", "الحمد لله", "لا إله إلا الله", "الله أكبر"]

def get_random_zekr() -> str:
    return random.choice(_LIST)
