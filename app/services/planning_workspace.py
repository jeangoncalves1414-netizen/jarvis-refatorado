"""Persistent, user-controlled planning workspaces for Jarvis conversations."""
from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any


class PlanningWorkspaceService:
    """Stores one lightweight planning document per chat session.

    The workspace is deliberately separate from the tutor whiteboard: planning
    is a long-lived personal artifact, while the whiteboard is lesson-specific.
    """

    def __init__(self, storage_path: str | Path = "data/planning_workspaces.json") -> None:
        self.storage_path = Path(storage_path)
        self._lock = threading.RLock()

    def _default_data(self) -> dict[str, Any]:
        return {"preferences": {"auto_open_for_planning": False}, "workspaces": {}}

    def _read(self) -> dict[str, Any]:
        if not self.storage_path.exists():
            return self._default_data()
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return self._default_data()
            data.setdefault("preferences", {})
            data.setdefault("workspaces", {})
            data["preferences"].setdefault("auto_open_for_planning", False)
            return data
        except (OSError, json.JSONDecodeError):
            return self._default_data()

    def _write(self, data: dict[str, Any]) -> None:
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary_path = tempfile.mkstemp(prefix="planning-", suffix=".json", dir=str(self.storage_path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.storage_path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    @staticmethod
    def _workspace(session_id: str, workspaces: dict[str, Any]) -> dict[str, Any]:
        return workspaces.setdefault(session_id, {
            "session_id": session_id,
            "title": "Plano em construção",
            "content": "# Plano em construção\n\n## Objetivo\n\n## Próximos passos\n\n## Decisões\n",
            "is_open": False,
            "updated_at": time.time(),
        })

    def get(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            workspace = self._workspace(session_id, data["workspaces"])
            return {"workspace": dict(workspace), "preferences": dict(data["preferences"])}

    def open(self, session_id: str, title: str = "") -> dict[str, Any]:
        with self._lock:
            data = self._read()
            workspace = self._workspace(session_id, data["workspaces"])
            if title.strip():
                workspace["title"] = title.strip()[:120]
                if workspace["content"].startswith("# Plano em construção"):
                    workspace["content"] = workspace["content"].replace("# Plano em construção", f"# {workspace['title']}", 1)
            workspace["is_open"] = True
            workspace["updated_at"] = time.time()
            self._write(data)
            return {"workspace": dict(workspace), "preferences": dict(data["preferences"])}

    def close(self, session_id: str) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            workspace = self._workspace(session_id, data["workspaces"])
            workspace["is_open"] = False
            workspace["updated_at"] = time.time()
            self._write(data)
            return {"workspace": dict(workspace), "preferences": dict(data["preferences"])}

    def update(self, session_id: str, *, title: str | None = None, content: str | None = None) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            workspace = self._workspace(session_id, data["workspaces"])
            if title is not None and title.strip():
                workspace["title"] = title.strip()[:120]
            if content is not None:
                workspace["content"] = content.strip()[:60_000]
            workspace["updated_at"] = time.time()
            self._write(data)
            return {"workspace": dict(workspace), "preferences": dict(data["preferences"])}

    def append(self, session_id: str, content: str) -> dict[str, Any]:
        text = content.strip()
        if not text:
            raise ValueError("O registro do plano não pode estar vazio.")
        with self._lock:
            data = self._read()
            workspace = self._workspace(session_id, data["workspaces"])
            workspace["content"] = f"{workspace['content'].rstrip()}\n\n- {text}"[:60_000]
            workspace["updated_at"] = time.time()
            self._write(data)
            return {"workspace": dict(workspace), "preferences": dict(data["preferences"])}

    def set_auto_open(self, enabled: bool) -> dict[str, Any]:
        with self._lock:
            data = self._read()
            data["preferences"]["auto_open_for_planning"] = bool(enabled)
            self._write(data)
            # Also record the explicit consent in the user's durable preference
            # store, so the conversational agent receives it in later sessions.
            try:
                from app.storage.memory_store import MemoryStore
                preference = (
                    "Abrir automaticamente o painel de planejamento em conversas de planejamento."
                    if enabled else "Perguntar antes de abrir o painel de planejamento."
                )
                MemoryStore().add_preference("planning_workspace_auto_open", preference)
            except Exception:
                pass
            return {"preferences": dict(data["preferences"])}


planning_workspace = PlanningWorkspaceService()
