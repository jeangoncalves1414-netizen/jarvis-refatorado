from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

DATA_DIR = os.path.join(os.getcwd(), "data")
ACTIVITY_FILE = os.path.join(DATA_DIR, "activity.json")
MAX_ENTRIES = 200

os.makedirs(DATA_DIR, exist_ok=True)


def _read() -> dict[str, Any]:
    if not os.path.exists(ACTIVITY_FILE):
        return {"entries": []}
    try:
        with open(ACTIVITY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"entries": []}


def _write(data: dict[str, Any]) -> None:
    with open(ACTIVITY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def log_activity(event_type: str, message: str, *, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = {
        "id": uuid.uuid4().hex[:12],
        "type": event_type,
        "message": message.strip(),
        "meta": meta or {},
        "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    data = _read()
    entries = data.setdefault("entries", [])
    entries.insert(0, entry)
    data["entries"] = entries[:MAX_ENTRIES]
    _write(data)
    return entry


def list_recent(limit: int = 20) -> list[dict[str, Any]]:
    entries = _read().get("entries", [])
    return list(entries[: max(1, min(limit, MAX_ENTRIES))])
