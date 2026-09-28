"""Local, profile-scoped goals and explicit proactive preferences."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any


VALID_POLICIES = {"ask_every_time", "planning_auto_open", "notify_only", "paused"}
VALID_STATUSES = {"active", "paused", "completed", "archived"}


class GoalStore:
    def __init__(self, path: str | Path = "data/goals.json") -> None:
        self.path = Path(path)
        self._lock = threading.RLock()

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "goals": [], "signals": [], "policy": "ask_every_time"}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            data.setdefault("goals", []); data.setdefault("signals", []); data.setdefault("policy", "ask_every_time")
            return data
        except (OSError, ValueError, json.JSONDecodeError):
            return {"version": 1, "goals": [], "signals": [], "policy": "ask_every_time"}

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix="goals-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output: json.dump(data, output, ensure_ascii=False, indent=2)
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp): os.unlink(temp)

    def list(self, profile_id: str = "default") -> list[dict[str, Any]]:
        with self._lock:
            return [dict(item) for item in self._read()["goals"] if item.get("profile_id") == profile_id]

    def create(self, title: str, next_action: str = "", *, profile_id: str = "default", cadence_days: int = 7, policy: str | None = None) -> dict[str, Any]:
        title = str(title).strip()
        if not title: raise ValueError("O objetivo precisa de um título.")
        if policy is not None and policy not in VALID_POLICIES: raise ValueError("Política proativa inválida.")
        with self._lock:
            data = self._read(); now = time.time()
            item = {"id": f"goal_{uuid.uuid4().hex}", "profile_id": profile_id, "title": title[:180], "next_action": str(next_action).strip()[:500], "status": "active", "policy": policy or data["policy"], "cadence_days": max(1, min(int(cadence_days), 90)), "quiet_hours": None, "last_intervention_at": 0, "feedback": "", "created_at": now, "updated_at": now}
            data["goals"].append(item); self._write(data); return dict(item)

    def update_status(self, goal_id: str, status: str) -> dict[str, Any] | None:
        if status not in VALID_STATUSES: raise ValueError("Status de objetivo inválido.")
        with self._lock:
            data = self._read()
            for goal in data["goals"]:
                if goal.get("id") == goal_id:
                    goal["status"] = status; goal["updated_at"] = time.time(); self._write(data); return dict(goal)
            return None

    def set_policy(self, policy: str) -> str:
        if policy not in VALID_POLICIES: raise ValueError("Política proativa inválida.")
        with self._lock:
            data = self._read(); data["policy"] = policy; self._write(data); return policy

    def record_signal(self, goal_id: str, reason: str, *, window_seconds: int = 3600) -> bool:
        """Deduplicate signals so a daemon cannot nag the user repeatedly."""
        with self._lock:
            data = self._read(); now = time.time()
            recent = any(item.get("goal_id") == goal_id and item.get("reason") == reason and now - float(item.get("at", 0)) < window_seconds for item in data["signals"])
            if recent: return False
            data["signals"].append({"goal_id": goal_id, "reason": reason[:180], "at": now})
            data["signals"] = data["signals"][-500:]; self._write(data); return True


goal_store = GoalStore()
