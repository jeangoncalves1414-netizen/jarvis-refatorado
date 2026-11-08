from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.storage import sync_tombstones

DATA_DIR = os.path.join(os.getcwd(), "data")
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
_lock = threading.Lock()

os.makedirs(DATA_DIR, exist_ok=True)


def _read() -> dict[str, Any]:
    try:
        with open(TASKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"tasks": []}
    if not isinstance(data, dict) or not isinstance(data.setdefault("tasks", []), list):
        raise ValueError("Formato inválido no arquivo de tarefas.")
    return data


def _write(data: dict[str, Any]) -> None:
    tmp = f"{TASKS_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, TASKS_FILE)


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
    with _lock:
        data = _read()
        data["tasks"].insert(0, task)
        _write(data)
    return task


def toggle_task(task_id: str) -> dict[str, Any] | None:
    with _lock:
        data = _read()
        for task in data["tasks"]:
            if task.get("id") == task_id:
                task["completed"] = not bool(task.get("completed"))
                task["updated_at"] = _now_iso()
                _write(data)
                return dict(task)
    return None


def delete_task(task_id: str) -> bool:
    with _lock:
        data = _read()
        tasks = data["tasks"]
        filtered = [t for t in tasks if t.get("id") != task_id]
        if len(filtered) == len(tasks):
            return False
        data["tasks"] = filtered
        _write(data)
    sync_tombstones.record("tasks", str(task_id))
    return True
