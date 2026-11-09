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

CANONICAL_WEEK_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

DAY_ALIASES: dict[str | int, str] = {
    0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun",
    "0": "mon", "1": "tue", "2": "wed", "3": "thu", "4": "fri", "5": "sat", "6": "sun",
    "seg": "mon", "segunda": "mon", "segunda-feira": "mon", "monday": "mon", "mon": "mon",
    "ter": "tue", "terça": "tue", "terca": "tue", "terça-feira": "tue", "terca-feira": "tue", "tuesday": "tue", "tue": "tue",
    "qua": "wed", "quarta": "wed", "quarta-feira": "wed", "wednesday": "wed", "wed": "wed",
    "qui": "thu", "quinta": "thu", "quinta-feira": "thu", "thursday": "thu", "thu": "thu",
    "sex": "fri", "sexta": "fri", "sexta-feira": "fri", "friday": "fri", "fri": "fri",
    "sab": "sat", "sáb": "sat", "sabado": "sat", "sábado": "sat", "saturday": "sat", "sat": "sat",
    "dom": "sun", "domingo": "sun", "sunday": "sun", "sun": "sun",
}

CANONICAL_TO_PT: dict[str, str] = {
    "mon": "seg", "tue": "ter", "wed": "qua", "thu": "qui", "fri": "sex", "sat": "sab", "sun": "dom"
}


def normalize_day(day: Any) -> str:
    """Converte dia da semana (índice 0-6, abreviação pt-BR ou en) para o código canônico mon..sun."""
    if isinstance(day, int):
        return DAY_ALIASES.get(day, "mon")
    clean = str(day or "").strip().lower()
    return DAY_ALIASES.get(clean, clean if clean in CANONICAL_WEEK_DAYS else "mon")


def normalize_days_list(days: Any) -> list[str]:
    """Normaliza lista de dias (aceita [0, 2, 4], ['seg', 'qua'], ['mon', 'wed'])."""
    if not days:
        return list(CANONICAL_WEEK_DAYS)
    if not isinstance(days, (list, tuple, set)):
        return list(CANONICAL_WEEK_DAYS)
    normalized: list[str] = []
    for d in days:
        norm = normalize_day(d)
        if norm in CANONICAL_WEEK_DAYS and norm not in normalized:
            normalized.append(norm)
    return normalized or list(CANONICAL_WEEK_DAYS)


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
                day_slots TEXT DEFAULT '{}',
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
        if "day_slots" not in columns:
            cursor.execute("ALTER TABLE habits ADD COLUMN day_slots TEXT DEFAULT '{}'")
        if "updated_at" not in columns:
            # Data da última alteração; 0 = nunca editado (a sincronização usa created_at nesse caso).
            cursor.execute("ALTER TABLE habits ADD COLUMN updated_at REAL DEFAULT 0")

        conn.commit()


init_db()


class HabitService:
    """Service to manage habits, streaks, granular schedules, and habit check-ins."""

    @staticmethod
    def _enrich_habit(habit: dict[str, Any]) -> dict[str, Any]:
        """Deserializa campos JSON e calcula slots modulares e streak do hábito."""
        try:
            habit["days_of_week"] = json.loads(habit.get("days_of_week") or '["mon","tue","wed","thu","fri","sat","sun"]')
        except Exception:
            habit["days_of_week"] = list(CANONICAL_WEEK_DAYS)

        try:
            habit["time_exceptions"] = json.loads(habit.get("time_exceptions") or '{}')
        except Exception:
            habit["time_exceptions"] = {}

        try:
            habit["items_list"] = json.loads(habit.get("items_list") or '[]')
        except Exception:
            habit["items_list"] = []

        try:
            habit["day_slots"] = json.loads(habit.get("day_slots") or '{}')
        except Exception:
            habit["day_slots"] = {}

        # Resolve o slot e substituição de hoje
        today_code = CANONICAL_WEEK_DAYS[date.today().weekday()]
        today_pt = CANONICAL_TO_PT.get(today_code, "seg")
        today_idx_str = str(date.today().weekday())
        today_idx = date.today().weekday()

        day_slots = habit["day_slots"]
        slot = (
            day_slots.get(today_code)
            or day_slots.get(today_pt)
            or day_slots.get(today_idx_str)
            or day_slots.get(today_idx)
        )
        habit["today_slot"] = slot

        if isinstance(slot, str) and slot.strip():
            habit["effective_title"] = slot.strip()
            habit["muscle_group"] = ""
        elif isinstance(slot, dict):
            habit["effective_title"] = (
                slot.get("title")
                or slot.get("activity")
                or slot.get("name")
                or habit.get("name", "")
            )
            habit["muscle_group"] = slot.get("muscle_group") or ""
        else:
            habit["effective_title"] = habit.get("name", "")
            habit["muscle_group"] = ""

        streak_info = HabitService.calculate_streak(habit["id"])
        habit["current_streak"] = streak_info["current_streak"]
        habit["best_streak"] = streak_info["best_streak"]
        habit["completed_today"] = HabitService.is_completed_today(habit["id"])
        return habit

    @staticmethod
    def create_habit(
        habit_id: str,
        name: str,
        category: str = "general",
        routine_block: str = "anytime",
        frequency_type: str = "daily",
        days_of_week: list[str | int] | None = None,
        start_time: str = "15:00",
        time_exceptions: dict[str, str] | None = None,
        items_list: list[str] | None = None,
        day_slots: dict[str, Any] | None = None,
        target_days_per_week: int = 7,
        target_value: float = 1.0,
        unit: str = "count",
        color: str = "#06b6d4",
        icon: str = "✨",
    ) -> dict[str, Any]:
        normalized_days = normalize_days_list(days_of_week)
        if time_exceptions is None:
            time_exceptions = {}
        if items_list is None:
            items_list = []
        if day_slots is None:
            day_slots = {}

        days_json = json.dumps(normalized_days, ensure_ascii=False)
        exceptions_json = json.dumps(time_exceptions, ensure_ascii=False)
        items_json = json.dumps(items_list, ensure_ascii=False)
        day_slots_json = json.dumps(day_slots, ensure_ascii=False)

        with get_db_connection() as conn:
            cursor = conn.cursor()
            now = time.time()
            cursor.execute(
                """
                INSERT OR REPLACE INTO habits 
                (id, name, category, routine_block, frequency_type, days_of_week, start_time, time_exceptions, items_list, day_slots, target_days_per_week, target_value, unit, color, icon, archived, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
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
                    day_slots_json,
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
            fields_to_update["days_of_week"] = json.dumps(normalize_days_list(kwargs["days_of_week"]), ensure_ascii=False)

        if "day_slots" in kwargs and kwargs["day_slots"] is not None:
            fields_to_update["day_slots"] = json.dumps(kwargs["day_slots"], ensure_ascii=False)

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
            return HabitService._enrich_habit(dict(row))

    @staticmethod
    def list_habits(include_archived: bool = False) -> list[dict[str, Any]]:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM habits" + ("" if include_archived else " WHERE archived = 0") + " ORDER BY created_at ASC"
            cursor.execute(query)
            rows = cursor.fetchall()
            return [HabitService._enrich_habit(dict(r)) for r in rows]

    @staticmethod
    def get_slot_for_day(habit_id: str, day: Any = None) -> Any:
        """Retorna a configuração/substituição do slot para um dia específico."""
        habit = HabitService.get_habit(habit_id)
        if not habit:
            return None
        norm = normalize_day(day if day is not None else date.today().weekday())
        pt = CANONICAL_TO_PT.get(norm, "seg")
        slots = habit.get("day_slots") or {}
        return slots.get(norm) or slots.get(pt) or slots.get(str(day)) or slots.get(day)

    @staticmethod
    def set_day_slot(habit_id: str, day: Any, slot_data: Any) -> dict[str, Any] | None:
        """Define ou atualiza a substituição de um dia no hábito."""
        habit = HabitService.get_habit(habit_id)
        if not habit:
            return None
        norm = normalize_day(day)
        current_slots = dict(habit.get("day_slots") or {})
        current_slots[norm] = slot_data
        return HabitService.update_habit(habit_id, day_slots=current_slots)

    @staticmethod
    def contextual_auto_check(
        text: str = "",
        event_type: str = "dialogue",
        data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Marca hábitos automaticamente com base no contexto do diálogo ou ações do sistema.

        Exemplo:
        - Saudação matinal ('bom dia', 'acordei') marca 'Acordar' / 'Levantar'
        - Ingestão de água marca 'Beber água'
        - Treino/academia marca 'Treino'
        """
        raw = (text or "").strip().lower()
        evt = (event_type or "").strip().lower()
        checked_habits: list[dict[str, Any]] = []

        is_morning = any(w in raw for w in ("bom dia", "acordei", "já acordei", "acabei de acordar", "levantando", "de pé", "acordar")) or evt in ("morning_greeting", "wake_up")
        is_water = any(w in raw for w in ("bebi água", "tomei água", "copo d'água", "copo de água", "bebi agua")) or evt in ("water_added", "add_water")
        is_workout = any(w in raw for w in ("terminei o treino", "treino feito", "fui pra academia", "malhei hoje", "treinei")) or evt in ("workout_completed", "workout")
        is_finance = any(w in raw for w in ("anotei gastos", "registrei despesa", "gasto anotado")) or evt in ("finance_added", "finance")

        if not (is_morning or is_water or is_workout or is_finance):
            return []

        active_habits = HabitService.list_habits()
        today_code = CANONICAL_WEEK_DAYS[date.today().weekday()]

        for habit in active_habits:
            habit_days = habit.get("days_of_week") or list(CANONICAL_WEEK_DAYS)
            if today_code not in habit_days:
                continue
            if habit.get("completed_today"):
                continue

            h_name = (habit.get("name") or "").lower()
            matched = False
            notes = ""

            if is_morning and any(k in h_name for k in ("acordar", "levantar", "despertar", "matinal")):
                matched = True
                notes = "Auto-check contextual: saudação matinal"
            elif is_water and any(k in h_name for k in ("água", "agua", "hidrat")):
                matched = True
                notes = "Auto-check contextual: hidratação"
            elif is_workout and any(k in h_name for k in ("treino", "academia", "musculação", "exercício", "exercicio")):
                matched = True
                notes = "Auto-check contextual: treino realizado"
            elif is_finance and any(k in h_name for k in ("finança", "financas", "gasto", "despesa")):
                matched = True
                notes = "Auto-check contextual: finanças registradas"

            if matched:
                updated = HabitService.check_in(habit["id"], notes=notes)
                checked_habits.append(updated)

        return checked_habits

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
