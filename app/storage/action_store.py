"""Append-only, bounded local journal for Action Kernel records."""
from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Iterable

from app.core.actions import ALLOWED_TRANSITIONS, ActionRecord, TERMINAL_STATUSES
from app.core.diagnostics import record


class ActionStore:
    def __init__(self, path: str | Path = "data/action_journal.jsonl", max_records: int = 2_000) -> None:
        self.path = Path(path)
        self.max_records = max_records
        self._lock = threading.RLock()
        self._records: dict[str, ActionRecord] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not self.path.exists():
            return
        try:
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    action = ActionRecord.from_dict(json.loads(line))
                    self._records[action.id] = action
        except (OSError, ValueError, json.JSONDecodeError):
            # A broken historical journal must never stop Jarvis from working.
            self._records = {}

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        items = sorted(self._records.values(), key=lambda item: item.updated_at)
        if len(items) > self.max_records:
            removable = [item for item in items if item.status in TERMINAL_STATUSES]
            for item in removable[:len(items) - self.max_records]:
                self._records.pop(item.id, None)
            items = sorted(self._records.values(), key=lambda item: item.updated_at)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text("\n".join(json.dumps(asdict(item), ensure_ascii=False) for item in items) + ("\n" if items else ""), encoding="utf-8")
        temporary.replace(self.path)

    def create(self, action: ActionRecord) -> ActionRecord:
        with self._lock:
            self._load()
            if action.id in self._records:
                raise ValueError("ID de ação já existe.")
            self._records[action.id] = action
            self._persist()
            record("action_kernel", "action_created", correlation_id=action.correlation_id, action_id=action.id, tool=action.tool_name, risk=action.risk)
            return action

    def get(self, action_id: str) -> ActionRecord | None:
        with self._lock:
            self._load()
            return self._records.get(action_id)

    def transition(self, action_id: str, status: str, *, result_summary: str | None = None, receipt_reference: str | None = None, undo_payload: dict | None = None) -> ActionRecord:
        with self._lock:
            self._load()
            current = self._records.get(action_id)
            if not current:
                raise KeyError("Ação não encontrada.")
            if status not in ALLOWED_TRANSITIONS.get(current.status, frozenset()):
                raise ValueError(f"Transição inválida: {current.status} → {status}")
            updated = ActionRecord(**{
                **asdict(current), "status": status, "updated_at": time.time(),
                "result_summary": result_summary if result_summary is not None else current.result_summary,
                "receipt_reference": receipt_reference if receipt_reference is not None else current.receipt_reference,
                "undo_payload": undo_payload if undo_payload is not None else current.undo_payload,
            })
            self._records[action_id] = updated
            self._persist()
            record("action_kernel", "action_transition", correlation_id=updated.correlation_id, action_id=updated.id, status=status)
            return updated

    def list(self, *, limit: int = 100, status: str | None = None) -> list[ActionRecord]:
        with self._lock:
            self._load()
            items: Iterable[ActionRecord] = self._records.values()
            if status:
                items = (item for item in items if item.status == status)
            return sorted(items, key=lambda item: item.updated_at, reverse=True)[:max(1, min(limit, 500))]


action_store = ActionStore()
