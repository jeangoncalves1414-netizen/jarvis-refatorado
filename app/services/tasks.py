"""Task & Checklist Management Service (inspired by Super Productivity & Todoist).

Manages tasks, subtasks, priorities (P1 Urgent to P4 Low), due dates, and completion status.
Stores data in persistent SQLite database (data/lifestyle.db).
"""
from __future__ import annotations

import sqlite3
import time
from datetime import datetime, date
from pathlib import Path
from typing import Any

from app.services.habits import get_db_connection
from app.storage import sync_tombstones


def init_task_tables() -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority INTEGER DEFAULT 3, -- 1=P1 (Urgent), 2=P2 (High), 3=P3 (Medium), 4=P4 (Low)
                project TEXT DEFAULT 'Geral',
                due_date TEXT DEFAULT '',    -- YYYY-MM-DD
                completed INTEGER DEFAULT 0,
                completed_at REAL DEFAULT NULL,
                created_at REAL NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_subtasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                title TEXT NOT NULL,
                completed INTEGER DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
        conn.commit()


init_task_tables()


class TaskService:
    """Service to handle tasks, checklists, and priorities."""

    @staticmethod
    def import_legacy_tasks() -> None:
        """Import old IDs once, retaining the JSON as a recovery copy."""
        import json
        from app.storage import task_store
        try:
            records = task_store._read().get("tasks", [])
        except (OSError, ValueError, json.JSONDecodeError):
            return
        if not records:
            return
        with get_db_connection() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS imported_legacy_tasks (id TEXT PRIMARY KEY)")
            for record in records:
                if not isinstance(record, dict) or not record.get("id") or not record.get("title"):
                    continue
                imported = conn.execute("INSERT OR IGNORE INTO imported_legacy_tasks VALUES (?)", (str(record["id"]),))
                if not imported.rowcount:
                    continue
                priority = {"high": 2, "normal": 3, "low": 4}.get(record.get("priority"), 3)
                try:
                    created = datetime.fromisoformat(record.get("created_at", "")).timestamp()
                except (TypeError, ValueError):
                    created = time.time()
                conn.execute("INSERT OR IGNORE INTO tasks (id,title,priority,completed,created_at) VALUES (?,?,?,?,?)",
                             (str(record["id"]), str(record["title"]), priority, int(bool(record.get("completed"))), created))

    @staticmethod
    def set_completed(task_id: str, completed: bool) -> dict[str, Any] | None:
        TaskService.import_legacy_tasks()
        with get_db_connection() as conn:
            conn.execute("UPDATE tasks SET completed = ?, completed_at = CASE WHEN ? = 0 THEN NULL WHEN completed = 0 THEN ? ELSE completed_at END WHERE id = ?",
                         (int(completed), int(completed), time.time(), task_id))
        return TaskService.get_task(task_id)

    @staticmethod
    def create_task(
        task_id: str,
        title: str,
        description: str = "",
        priority: int = 3,
        project: str = "Geral",
        due_date: str = "",
        subtasks: list[str] | None = None,
    ) -> dict[str, Any]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                INSERT OR REPLACE INTO tasks (id, title, description, priority, project, due_date, completed, completed_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 0, NULL, ?)
            """,
                (task_id, title, description, priority, project, due_date, now),
            )
            if subtasks:
                for sub in subtasks:
                    cursor.execute(
                        "INSERT INTO task_subtasks (task_id, title, completed) VALUES (?, ?, 0)",
                        (task_id, sub),
                    )
            conn.commit()
        return TaskService.get_task(task_id)

    @staticmethod
    def get_task(task_id: str) -> dict[str, Any] | None:
        TaskService.import_legacy_tasks()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            task = dict(row)
            cursor.execute("SELECT id, title, completed FROM task_subtasks WHERE task_id = ?", (task_id,))
            task["subtasks"] = [dict(s) for s in cursor.fetchall()]
            return task

    @staticmethod
    def list_tasks(completed: bool | None = False, project: str = "") -> list[dict[str, Any]]:
        TaskService.import_legacy_tasks()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM tasks WHERE 1=1"
            params: list[Any] = []
            if completed is not None:
                query += " AND completed = ?"
                params.append(1 if completed else 0)
            if project:
                query += " AND project = ?"
                params.append(project)
            query += " ORDER BY priority ASC, created_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            results = []
            for r in rows:
                t = dict(r)
                cursor.execute("SELECT id, title, completed FROM task_subtasks WHERE task_id = ?", (t["id"],))
                t["subtasks"] = [dict(s) for s in cursor.fetchall()]
                results.append(t)
            return results

    @staticmethod
    def toggle_task(task_id: str) -> dict[str, Any] | None:
        task = TaskService.get_task(task_id)
        if not task:
            return None
        new_status = 0 if task["completed"] == 1 else 1
        now = time.time() if new_status == 1 else None
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE tasks SET completed = ?, completed_at = ? WHERE id = ?", (new_status, now, task_id))
            conn.commit()
        return TaskService.get_task(task_id)

    @staticmethod
    def update_task(
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: int | None = None,
        project: str | None = None,
        due_date: str | None = None,
    ) -> dict[str, Any] | None:
        """Altera só os campos informados. Retorna None se a tarefa não existir."""
        if not TaskService.get_task(task_id):
            return None
        fields = {
            key: value
            for key, value in (("title", title), ("description", description), ("priority", priority), ("project", project), ("due_date", due_date))
            if value is not None
        }
        if fields:
            set_clause = ", ".join(f"{column} = ?" for column in fields)
            with get_db_connection() as conn:
                conn.cursor().execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", [*fields.values(), task_id])
                conn.commit()
        return TaskService.get_task(task_id)

    @staticmethod
    def delete_task(task_id: str) -> bool:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM task_subtasks WHERE task_id = ?", (task_id,))
            cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            removed = cursor.rowcount > 0
            conn.commit()
        if removed:
            sync_tombstones.record("lifestyle.tasks", sync_tombstones.row_key(task_id))
        return removed
