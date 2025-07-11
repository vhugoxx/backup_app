# settings.py
from __future__ import annotations
import json, sys
from pathlib import Path
from typing import Any, Dict

_CFG = Path(__file__).with_name("settings.json")
_DATA: Dict[str, Any] = {}

def load() -> None:
    global _DATA
    if _CFG.exists():
        try:
            _DATA = json.loads(_CFG.read_text(encoding="utf-8"))
        except Exception:
            _DATA = {}

def get(key: str, default: Any = None) -> Any:
    return _DATA.get(key, default)

def set(key: str, value: Any) -> None:
    _DATA[key] = value

def save() -> None:
    try:
        _CFG.write_text(json.dumps(_DATA, indent=2, ensure_ascii=False))
    except Exception as exc:   # nunca deixar falhar o fecho da app
        print(f"[settings] warning: {exc}", file=sys.stderr)

load()
