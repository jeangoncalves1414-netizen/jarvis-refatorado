from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, storage_path: str | None = None) -> None:
        self.storage_path = Path(storage_path or "data/memory.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {"preferences": [], "facts": []}
        self._load()

    def _load(self) -> None:
        if not self.storage_path.exists():
            return
        try:
            self._data = json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {"preferences": [], "facts": []}

    def _save(self) -> None:
        self.storage_path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_preference(self, key: str, value: str) -> None:
        self._data.setdefault("preferences", []).append({"key": key, "value": value})
        self._save()

    def get_preferences(self) -> list[dict[str, str]]:
        return list(self._data.get("preferences", []))

    def add_fact(self, fact: str) -> None:
        self._data.setdefault("facts", []).append(fact)
        self._save()

    def get_facts(self) -> list[str]:
        return list(self._data.get("facts", []))
