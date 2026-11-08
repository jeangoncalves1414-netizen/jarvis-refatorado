"""Habit & Routine Management Service (inspired by Loop Habit Tracker & Habitica).

Manages daily habits, habit streaks, habit score calculation, and routine blocks (Morning/Afternoon/Evening).
Supports granular schedule days, custom start times, day-specific time exceptions, and item/subject lists.
Stores data in a persistent SQLite database (data/lifestyle.db).
"""
from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any

from app.storage import sync_tombstones


DB_PATH = Path("data/lifestyle.db")


def get_db_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habits (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                routine_block TEXT DEFAULT 'anytime', -- morning, afternoon, evening, anytime
                frequency_type TEXT DEFAULT 'daily',   -- daily, weekly, custom
                days_of_week TEXT DEFAULT '["mon","tue","wed","thu","fri","sat","sun"]',
                start_time TEXT DEFAULT '15:00',
                time_exceptions TEXT DEFAULT '{}',
                items_list TEXT DEFAULT '[]',
                target_days_per_week INTEGER DEFAULT 7,
                target_value REAL DEFAULT 1.0,
                unit TEXT DEFAULT 'count',
                color TEXT DEFAULT '#06b6d4',
                icon TEXT DEFAULT '✨',
                archived INTEGER DEFAULT 0,
                created_at REAL NOT NULL,
                updated_at REAL DEFAULT 0
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS habit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                habit_id TEXT NOT NULL,
                date_str TEXT NOT NULL, -- YYYY-MM-DD
                value REAL DEFAULT 1.0,
                completed INTEGER DEFAULT 1,
                notes TEXT DEFAULT '',
                timestamp REAL NOT NULL,
                FOREIGN KEY (habit_id) REFERENCES habits(id) ON DELETE CASCADE,
                UNIQUE(habit_id, date_str)
            )
        """)

        # Safely migrate existing tables if columns are missing
        cursor.execute("PRAGMA table_info(habits)")
        columns = [column[1] for column in cursor.fetchall()]
        if "days_of_week" not in columns:
            cursor.execute("ALTER TABLE habits ADD COLUMN days_of_week TEXT DEFAULT '[\"mon\",\"tue\",\"wed\",\"thu\",\"fri\",\"sat\",\"sun\"]'")
        if "start_time" not in columns:
            cursor.execute("ALTER TABLE habits ADD COLUMN start_time TEXT DEFAULT '15:00'")
        if "time_exceptions" not in columns:
            cursor.execute("ALTER TABLE habits ADD COLUMN time_exceptions TEXT DEFAULT '{}'")
        if "items_list" not in columns:
            cursor.execute("ALTER TABLE habits ADD COLUMN items_list TEXT DEFAULT '[]'")
        if "updated_at" not in columns:
            # Data da última alteração; 0 = nunca editado (a sincronização usa created_at nesse caso).
            cursor.execute("ALTER TABLE habits ADD COLUMN updated_at REAL DEFAULT 0")

        conn.commit()


init_db()


class HabitService:
    """Service to manage habits, streaks, granular schedules, and habit check-ins."""

    @staticmethod
    def create_habit(
        habit_id: str,
        name: str,
        category: str = "general",
        routine_block: str = "anytime",
        frequency_type: str = "daily",
        days_of_week: list[str] | None = None,
        start_time: str = "15:00",
        time_exceptions: dict[str, str] | None = None,
        items_list: list[str] | None = None,
        target_days_per_week: int = 7,
        target_value: float = 1.0,
        unit: str = "count",
        color: str = "#06b6d4",
        icon: str = "✨",
    ) -> dict[str, Any]:
        if days_of_week is None:
            days_of_week = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if time_exceptions is None:
            time_exceptions = {}
        if items_list is None:
            items_list = []

        days_json = json.dumps(days_of_week, ensure_ascii=False)
        exceptions_json = json.dumps(time_exceptions, ensure_ascii=False)
        items_json = json.dumps(items_list, ensure_ascii=False)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                INSERT OR REPLACE INTO habits 
                (id, name, category, routine_block, frequency_type, days_of_week, start_time, time_exceptions, items_list, target_days_per_week, target_value, unit, color, icon, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
            """,
                (
                    habit_id,
                    name,
                    category,
                    routine_block,
                    frequency_type,
                    days_json,
                    start_time,
                    exceptions_json,
                    items_json,
                    target_days_per_week,
                    target_value,
                    unit,
                    color,
                    icon,
                    now,
                    now,
                ),
            )
            conn.commit()
        return HabitService.get_habit(habit_id)

    @staticmethod
    def update_habit(habit_id: str, **kwargs: Any) -> dict[str, Any] | None:
        habit = HabitService.get_habit(habit_id)
        if not habit:
            return None

        fields_to_update = {}
        for key in ("name", "category", "routine_block", "frequency_type", "start_time", "color", "icon"):
            if key in kwargs and kwargs[key] is not None:
                fields_to_update[key] = str(kwargs[key])

        if "days_of_week" in kwargs and kwargs["days_of_week"] is not None:
            fields_to_update["days_of_week"] = json.dumps(kwargs["days_of_week"], ensure_ascii=False)

        if "time_exceptions" in kwargs and kwargs["time_exceptions"] is not None:
            fields_to_update["time_exceptions"] = json.dumps(kwargs["time_exceptions"], ensure_ascii=False)

        if "items_list" in kwargs and kwargs["items_list"] is not None:
            fields_to_update["items_list"] = json.dumps(kwargs["items_list"], ensure_ascii=False)

        if not fields_to_update:
            return habit

        fields_to_update["updated_at"] = time.time()
        set_clause = ", ".join(f"{col} = ?" for col in fields_to_update.keys())
        params = list(fields_to_update.values())
        params.append(habit_id)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"UPDATE habits SET {set_clause} WHERE id = ?", params)
            conn.commit()

        return HabitService.get_habit(habit_id)

    @staticmethod
    def get_habit(habit_id: str) -> dict[str, Any] | None:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM habits WHERE id = ?", (habit_id,))
            row = cursor.fetchone()
            if not row:
                return None
            habit = dict(row)
            try:
                habit["days_of_week"] = json.loads(habit.get("days_of_week") or '["mon","tue","wed","thu","fri","sat","sun"]')
            except Exception:
                habit["days_of_week"] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

            try:
                habit["time_exceptions"] = json.loads(habit.get("time_exceptions") or '{}')
            except Exception:
                habit["time_exceptions"] = {}

            try:
                habit["items_list"] = json.loads(habit.get("items_list") or '[]')
            except Exception:
                habit["items_list"] = []

            streak_info = HabitService.calculate_streak(habit_id)
            habit["current_streak"] = streak_info["current_streak"]
            habit["best_streak"] = streak_info["best_streak"]
            habit["completed_today"] = HabitService.is_completed_today(habit_id)
            return habit

    @staticmethod
    def list_habits(include_archived: bool = False) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM habits" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY created_at ASC"
            cursor.execute(query)
            rows = cursor.fetchall()
            results = []
            for row in rows:
                h = dict(row)
                try:
                    h["days_of_week"] = json.loads(h.get("days_of_week") or '["mon","tue","wed","thu","fri","sat","sun"]')
                except Exception:
                    h["days_of_week"] = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

                try:
                    h["time_exceptions"] = json.loads(h.get("time_exceptions") or '{}')
                except Exception:
                    h["time_exceptions"] = {}

                try:
                    h["items_list"] = json.loads(h.get("items_list") or '[]')
                except Exception:
                    h["items_list"] = []

                streak = HabitService.calculate_streak(h["id"])
                h["current_streak"] = streak["current_streak"]
                h["best_streak"] = streak["best_streak"]
                h["completed_today"] = HabitService.is_completed_today(h["id"])
                results.append(h)
            return results

    @staticmethod
    def check_in(habit_id: str, date_str: str = "", value: float = 1.0, notes: str = "") -> dict[str, Any]:
        if not date_str:
            date_str = date.today().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                INSERT INTO habit_logs (habit_id, date_str, value, completed, notes, timestamp)
                VALUES (?, ?, ?, 1, ?, ?)
                ON CONFLICT(habit_id, date_str) DO UPDATE SET
                    value = excluded.value,
                    completed = 1,
                    notes = excluded.notes,
                    timestamp = excluded.timestamp
            """,
                (habit_id, date_str, value, notes, now),
            )
            conn.commit()
        return HabitService.get_habit(habit_id) or {"ok": True, "habit_id": habit_id}

    @staticmethod
    def uncheck_in(habit_id: str, date_str: str = "") -> dict[str, Any]:
        if not date_str:
            date_str = date.today().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM habit_logs WHERE habit_id = ? AND date_str = ?", (habit_id, date_str))
            removed = cursor.rowcount > 0
            conn.commit()
        if removed:
            sync_tombstones.record("lifestyle.habit_logs", sync_tombstones.row_key(habit_id, date_str))
        return HabitService.get_habit(habit_id) or {"ok": True, "habit_id": habit_id}

    @staticmethod
    def is_completed_today(habit_id: str) -> bool:
        today_str = date.today().isoformat()
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT completed FROM habit_logs WHERE habit_id = ? AND date_str = ?", (habit_id, today_str))
            row = cursor.fetchone()
            return bool(row and row["completed"] == 1)

    @staticmethod
    def calculate_streak(habit_id: str) -> dict[str, int]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT date_str FROM habit_logs WHERE habit_id = ? AND completed = 1 ORDER BY date_str DESC",
                (habit_id,),
            )
            rows = cursor.fetchall()
            if not rows:
                return {"current_streak": 0, "best_streak": 0}

            dates = [date.fromisoformat(r["date_str"]) for r in rows]
            dates_set = set(dates)

            today = date.today()
            yesterday = today - timedelta(days=1)

            current_streak = 0
            curr_date = today if today in dates_set else (yesterday if yesterday in dates_set else None)

            if curr_date:
                while curr_date in dates_set:
                    current_streak += 1
                    curr_date -= timedelta(days=1)

            best_streak = 0
            if dates:
                sorted_dates = sorted(list(dates_set))
                temp_streak = 1
                best_streak = 1
                for i in range(1, len(sorted_dates)):
                    if sorted_dates[i] == sorted_dates[i - 1] + timedelta(days=1):
                        temp_streak += 1
                        if temp_streak > best_streak:
                            best_streak = temp_streak
                    else:
                        temp_streak = 1

            return {"current_streak": current_streak, "best_streak": max(best_streak, current_streak)}

    @staticmethod
    def get_heatmap_30_days() -> list[dict[str, Any]]:
        """Retorna matriz de consistência dos últimos 30 dias (30-day heatmap data)."""
        today = date.today()
        dates_30 = [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) as total_habits FROM habits WHERE archived = 0")
            total_habits = cursor.fetchone()["total_habits"] or 1

            cursor.execute(
                "SELECT date_str, count(*) as completed_count FROM habit_logs WHERE completed = 1 GROUP BY date_str"
            )
            logs_map = {row["date_str"]: row["completed_count"] for row in cursor.fetchall()}

            matrix = []
            for d in dates_30:
                completed = logs_map.get(d, 0)
                rate = min(1.0, completed / max(1, total_habits))
                matrix.append({"date": d, "completed_count": completed, "rate": round(rate, 2)})
            return matrix

    @staticmethod
    def delete_habit(habit_id: str) -> bool:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM habit_logs WHERE habit_id = ?", (habit_id,))
            cursor.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
            removed = cursor.rowcount > 0
            conn.commit()
        if removed:
            sync_tombstones.record("lifestyle.habits", sync_tombstones.row_key(habit_id))
        return removed
