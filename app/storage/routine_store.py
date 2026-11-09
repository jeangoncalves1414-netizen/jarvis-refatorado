"""Rotinas e histórico de execuções em SQLite local (``data/routines.sqlite3``).

Rotinas não sincronizam com o celular nem com a nuvem: os gatilhos dependem deste PC (horário,
voz, comandos) e as etapas usam ferramentas locais. Quem usa resolve ``routine_store`` deste
módulo na hora da chamada, para os testes trocarem o arquivo por um em ``tmp_path``.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from pathlib import Path
from typing import Any

MAX_HISTORY = 200
RUN_STATUSES = frozenset({"running", "paused", "succeeded", "failed", "cancelled", "skipped", "missed", "interrupted", "alert"})
_ROUTINE_FIELDS = ("name", "enabled", "steps", "triggers", "quiet", "catch_up_minutes")
_LAST_FIELDS = ("last_scheduled_for", "last_run_at", "last_status", "last_run_id", "last_summary")
_RUN_FIELDS = ("run_id", "finished_at", "status", "step_index", "summary")


class RoutineStore:
    def __init__(self, path: str | Path = "data/routines.sqlite3") -> None:
        self.path = Path(path)
        self._lock = threading.RLock()
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        if not self._initialized:
            with db:
                db.execute(
                    "CREATE TABLE IF NOT EXISTS routines (id TEXT PRIMARY KEY, name TEXT NOT NULL, enabled INTEGER NOT NULL,"
                    " steps_json TEXT NOT NULL, triggers_json TEXT NOT NULL, quiet_json TEXT, catch_up_minutes INTEGER NOT NULL,"
                    " created_at REAL NOT NULL, updated_at REAL NOT NULL, last_scheduled_for REAL, last_run_at REAL,"
                    " last_status TEXT, last_run_id TEXT, last_summary TEXT)"
                )
                db.execute(
                    "CREATE TABLE IF NOT EXISTS routine_runs (id TEXT PRIMARY KEY, routine_id TEXT NOT NULL, run_id TEXT,"
                    " trigger_kind TEXT NOT NULL, scheduled_for REAL, started_at REAL NOT NULL, finished_at REAL,"
                    " status TEXT NOT NULL, step_index INTEGER NOT NULL DEFAULT 0, summary TEXT)"
                )
                db.execute("CREATE INDEX IF NOT EXISTS routine_runs_by_routine ON routine_runs(routine_id, started_at DESC)")
            self._initialized = True
        return db

    # ── rotinas ────────────────────────────────────────────────────────────────
    @staticmethod
    def _routine(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"], "name": row["name"], "enabled": bool(row["enabled"]),
            "steps": json.loads(row["steps_json"]), "triggers": json.loads(row["triggers_json"]),
            "quiet": json.loads(row["quiet_json"]) if row["quiet_json"] else None,
            "catch_up_minutes": int(row["catch_up_minutes"]),
            "created_at": row["created_at"], "updated_at": row["updated_at"],
            **{name: row[name] for name in _LAST_FIELDS},
        }

    @staticmethod
    def _columns(fields: dict[str, Any]) -> dict[str, Any]:
        columns: dict[str, Any] = {}
        for name in _ROUTINE_FIELDS:
            if name not in fields:
                continue
            value = fields[name]
            if name == "enabled":
                columns["enabled"] = 1 if value else 0
            elif name in ("steps", "triggers"):
                columns[f"{name}_json"] = json.dumps(value, ensure_ascii=False)
            elif name == "quiet":
                columns["quiet_json"] = json.dumps(value, ensure_ascii=False) if value else None
            elif name == "catch_up_minutes":
                columns["catch_up_minutes"] = int(value) if value is not None else None
            elif name in ("name", "id"):
                columns[name] = str(value)
            else:
                columns[name] = value
        return columns

    def create(self, fields: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        routine_id = f"rt_{uuid.uuid4().hex[:12]}"
        columns = {"id": routine_id, "name": fields["name"], **self._columns(fields), "created_at": now, "updated_at": now}
        with self._lock, closing(self._connect()) as db, db:
            db.execute(f"INSERT INTO routines({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})", tuple(columns.values()))
        return self.get(routine_id)

    def get(self, routine_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM routines WHERE id = ?", (routine_id,)).fetchone()
        return self._routine(row) if row else None

    def list(self) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM routines ORDER BY created_at").fetchall()
        return [self._routine(row) for row in rows]

    def update(self, routine_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        columns = self._columns(fields)
        if "name" in fields:
            columns["name"] = fields["name"]
        columns["updated_at"] = time.time()
        with self._lock, closing(self._connect()) as db, db:
            cursor = db.execute(f"UPDATE routines SET {', '.join(f'{key} = ?' for key in columns)} WHERE id = ?", (*columns.values(), routine_id))
            if cursor.rowcount == 0:
                raise KeyError("Rotina não encontrada.")
        return self.get(routine_id)

    def set_enabled(self, routine_id: str, enabled: bool) -> dict[str, Any]:
        return self.update(routine_id, {"enabled": bool(enabled)})

    def set_last(self, routine_id: str, **fields: Any) -> None:
        """Último disparo e último resultado (não muda ``updated_at``)."""
        clean = {key: value for key, value in fields.items() if key in _LAST_FIELDS}
        if not clean:
            return
        with self._lock, closing(self._connect()) as db, db:
            db.execute(f"UPDATE routines SET {', '.join(f'{key} = ?' for key in clean)} WHERE id = ?", (*clean.values(), routine_id))

    def delete(self, routine_id: str) -> bool:
        with self._lock, closing(self._connect()) as db, db:
            deleted = db.execute("DELETE FROM routines WHERE id = ?", (routine_id,)).rowcount
            db.execute("DELETE FROM routine_runs WHERE routine_id = ?", (routine_id,))
        return bool(deleted)

    # ── histórico ──────────────────────────────────────────────────────────────
    def add_run(self, routine_id: str, trigger_kind: str, *, status: str = "running", run_id: str | None = None,
                scheduled_for: float | None = None, summary: str = "", step_index: int = 0) -> dict[str, Any]:
        if status not in RUN_STATUSES:
            raise ValueError(f"Status de execução inválido: {status}")
        now = time.time()
        row = {
            "id": f"rr_{uuid.uuid4().hex[:12]}", "routine_id": routine_id, "run_id": run_id, "trigger_kind": str(trigger_kind)[:40],
            "scheduled_for": scheduled_for, "started_at": now, "finished_at": None if status in ("running", "paused") else now,
            "status": status, "step_index": int(step_index), "summary": str(summary or "")[:500],
        }
        with self._lock, closing(self._connect()) as db, db:
            db.execute(f"INSERT INTO routine_runs({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})", tuple(row.values()))
            # Poda: só as 200 execuções mais recentes de cada rotina.
            db.execute(
                "DELETE FROM routine_runs WHERE routine_id = ? AND id NOT IN "
                "(SELECT id FROM routine_runs WHERE routine_id = ? ORDER BY started_at DESC, rowid DESC LIMIT ?)",
                (routine_id, routine_id, MAX_HISTORY),
            )
        return row

    def update_run(self, entry_id: str, **fields: Any) -> None:
        clean = {key: value for key, value in fields.items() if key in _RUN_FIELDS}
        if "status" in clean and clean["status"] not in RUN_STATUSES:
            raise ValueError(f"Status de execução inválido: {clean['status']}")
        if "summary" in clean:
            clean["summary"] = str(clean["summary"] or "")[:500]
        if not clean:
            return
        with self._lock, closing(self._connect()) as db, db:
            db.execute(f"UPDATE routine_runs SET {', '.join(f'{key} = ?' for key in clean)} WHERE id = ?", (*clean.values(), entry_id))

    def get_run(self, entry_id: str) -> dict[str, Any] | None:
        with self._lock, closing(self._connect()) as db:
            row = db.execute("SELECT * FROM routine_runs WHERE id = ?", (entry_id,)).fetchone()
        return dict(row) if row else None

    def history(self, routine_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM routine_runs WHERE routine_id = ? ORDER BY started_at DESC, rowid DESC LIMIT ?",
                              (routine_id, max(1, min(int(limit), MAX_HISTORY)))).fetchall()
        return [dict(row) for row in rows]

    def runs_with_status(self, *statuses: str) -> list[dict[str, Any]]:
        marks = ", ".join("?" for _ in statuses)
        with self._lock, closing(self._connect()) as db:
            rows = db.execute(f"SELECT * FROM routine_runs WHERE status IN ({marks}) ORDER BY started_at", statuses).fetchall()
        return [dict(row) for row in rows]

    def alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        with self._lock, closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM routine_runs WHERE status = 'alert' ORDER BY started_at DESC LIMIT ?",
                              (max(1, min(int(limit), MAX_HISTORY)),)).fetchall()
        return [dict(row) for row in rows]

    def mark_interrupted(self) -> int:
        """Reinício do backend: execuções em andamento ou pausadas não continuam sozinhas."""
        now = time.time()
        summary = "Backend reiniciado; a execução foi interrompida e não será retomada."
        with self._lock, closing(self._connect()) as db, db:
            rows = db.execute("SELECT id, routine_id FROM routine_runs WHERE status IN ('running', 'paused')").fetchall()
            db.execute("UPDATE routine_runs SET status = 'interrupted', finished_at = ?, summary = ? WHERE status IN ('running', 'paused')", (now, summary))
            for row in rows:
                db.execute("UPDATE routines SET last_status = 'interrupted', last_summary = ? WHERE id = ? AND last_status IN ('running', 'paused')",
                           (summary, row["routine_id"]))
        return len(rows)


routine_store = RoutineStore()
