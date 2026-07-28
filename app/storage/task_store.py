from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

DATA_DIR = os.path.join(os.getcwd(), "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _read() -> dict[str, Any]:
    if not os.path.exists(TASKS_FILE):
        return {"tasks": []}
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"tasks": []}


def _write(data: dict[str, Any]) -> None:
    with open(TASKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def list_tasks(*, include_completed: bool = True) -> list[dict[str, Any]]:
    tasks = _read().get("tasks", [])
    if include_completed:
        return list(tasks)
    return [t for t in tasks if not t.get("completed")]


def add_task(title: str, *, priority: str = "normal") -> dict[str, Any]:
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("O título da tarefa não pode ficar vazio.")
    task = {
        "id": uuid.uuid4().hex[:12],
        "title": cleaned,
        "completed": False,
        "priority": priority if priority in {"low", "normal", "high"} else "normal",
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    data = _read()
    data.setdefault("tasks", []).insert(0, task)
    _write(data)
    return task


def toggle_task(task_id: str) -> dict[str, Any] | None:
    data = _read()
    for task in data.get("tasks", []):
        if task.get("id") == task_id:
            task["completed"] = not bool(task.get("completed"))
            task["updated_at"] = _now_iso()
            _write(data)
            return dict(task)
    return None


def delete_task(task_id: str) -> bool:
    data = _read()
    tasks = data.get("tasks", [])
    filtered = [t for t in tasks if t.get("id") != task_id]
    if len(filtered) == len(tasks):
        return False
    data["tasks"] = filtered
    _write(data)
    return True
