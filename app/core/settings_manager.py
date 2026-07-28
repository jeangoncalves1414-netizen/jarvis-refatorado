from __future__ import annotations

import json
from pathlib import Path
from typing import Any


SETTINGS_FILE = Path("data/settings.json")


class SettingsManager:
    """Gerenciador de configurações."""
    
    def __init__(self):
        self._settings = self._load()
    
    def _load(self) -> dict:
        if not SETTINGS_FILE.exists():
            return {}
        try:
            return json.loads(SETTINGS_FILE.read_text())
        except Exception:
            return {}
    
    def save(self) -> None:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(self._settings, indent=2))
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self.save()
    
    def delete(self, key: str) -> None:
        self._settings.pop(key, None)
        self.save()
