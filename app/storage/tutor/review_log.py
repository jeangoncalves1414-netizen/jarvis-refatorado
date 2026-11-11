"""Append-only JSONL log of card reviews and undos."""
from __future__ import annotations

import copy
import json
import threading
import uuid
from pathlib import Path
from typing import Any

from app.storage.tutor.fsrs import SCHEDULING_KEYS


def snapshot(card: dict[str, Any]) -> dict[str, Any]:
    """Exact raw scheduling state of a card: values present plus keys absent."""
    return {
        "values": {key: copy.deepcopy(card[key]) for key in SCHEDULING_KEYS if key in card},
        "absent": [key for key in SCHEDULING_KEYS if key not in card],
    }


def restore(card: dict[str, Any], snap: dict[str, Any]) -> None:
    card.update(copy.deepcopy(snap.get("values") or {}))
    for key in snap.get("absent") or []:
        card.pop(key, None)


class ReviewLog:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def append(self, entry: dict[str, Any]) -> dict[str, Any]:
        entry = dict(entry)
        if "id" not in entry:
            prefix = "undo" if entry.get("type") == "undo" else "rev"
            entry["id"] = f"{prefix}-{uuid.uuid4().hex[:8]}"
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        return entry

    def entries(self) -> list[dict[str, Any]]:
        with self._lock:
            try:
                lines = self.path.read_text(encoding="utf-8").splitlines()
            except FileNotFoundError:
                return []
        result = []
        for line in lines:
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                result.append(entry)
        return result

    def active_reviews(self) -> list[dict[str, Any]]:
        entries = self.entries()
        undone = {e.get("target") for e in entries if e.get("type") == "undo"}
        return [e for e in entries if e.get("type") == "review" and e.get("id") not in undone]

    def last_active_review(self) -> dict[str, Any] | None:
        reviews = self.active_reviews()
        return reviews[-1] if reviews else None
