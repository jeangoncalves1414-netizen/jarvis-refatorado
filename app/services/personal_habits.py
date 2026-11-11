"""Shared panel/agent catalogue. Evolute records stay in their original store."""
from __future__ import annotations

from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import date
import time
from typing import Any

from app.services.habits import CANONICAL_WEEK_DAYS, HabitService as SqlHabits, get_db_connection, normalize_days_list
from app.services.lifeos import LifeOSService, _DB_LOCK


def public_evolute_id(raw_id: str) -> str:
    return "evo~" + urlsafe_b64encode(raw_id.encode()).decode().rstrip("=")


def _raw_id(key: str) -> str | None:
    if not key.startswith("evo~"):
        return None
    try:
        return urlsafe_b64decode(key[4:] + "===").decode()
    except (UnicodeError, ValueError):
        return None


def _evolute_row(habit: dict, bucket: dict, day: str) -> dict:
    raw_id = habit["id"]
    log = (bucket.get(f"lifeos_hlog_{day}") or {}).get(raw_id) or {}
    options = habit.get("jarvis") or {}
    name = habit.get("title") or habit.get("name") or raw_id
    return {
        **options, "source": "evolute", "id": public_evolute_id(raw_id), "name": name,
        "effective_title": name, "category": options.get("category", "general"),
        "routine_block": options.get("routine_block", "anytime"), "start_time": options.get("start_time", ""),
        "days_of_week": normalize_days_list(options.get("days_of_week")), "day_slots": options.get("day_slots", {}),
        "items_list": options.get("items_list", []), "time_exceptions": options.get("time_exceptions", {}),
        "icon": options.get("icon", "✨"), "target_value": habit.get("targetValue") or 1,
        "unit": habit.get("unit") or "count", "created_date": habit.get("createdAt"),
        "connectedTo": habit.get("connectedTo"), "isPriority": bool(habit.get("isPriority")),
        "current_streak": habit.get("streak") or 0, "best_streak": habit.get("bestStreak") or 0,
        "completed_today": bool(log.get("completed")), "completed_at": log.get("completed_at") if log.get("completed") else None,
        "current_value": log.get("currentValue", log.get("value")), "archived": bool(habit.get("archived")),
    }


class PersonalHabits(SqlHabits):
    @staticmethod
    def list_habits(include_archived: bool = False, *, day: str | None = None, scheduled: bool = False) -> list[dict]:
        day = day or date.today().isoformat()
        weekday = CANONICAL_WEEK_DAYS[date.fromisoformat(day).weekday()]
        rows = [dict(h, source="panel") for h in SqlHabits.list_habits(include_archived)]
        if day != date.today().isoformat():
            with get_db_connection() as conn:
                logs = {r["habit_id"]: r for r in conn.execute("SELECT * FROM habit_logs WHERE date_str = ?", (day,))}
            for row in rows:
                log = logs.get(row["id"])
                row["completed_today"] = bool(log and log["completed"])
                row["completed_at"] = log["timestamp"] if row["completed_today"] else None
        bucket = LifeOSService.get_data_bucket()
        rows.extend(_evolute_row(h, bucket, day) for h in bucket.get("lifeos_habits") or []
                    if isinstance(h, dict) and isinstance(h.get("id"), str) and (include_archived or not h.get("archived")))
        if scheduled:
            return [r for r in rows if weekday in r["days_of_week"] and (r.get("created_date") or day)[:10] <= day]
        return rows

    @staticmethod
    def get_habit(key: str) -> dict | None:
        raw = _raw_id(key)
        if raw is None:
            return SqlHabits.get_habit(key)
        bucket = LifeOSService.get_data_bucket()
        h = next((h for h in bucket.get("lifeos_habits") or [] if h.get("id") == raw), None)
        return _evolute_row(h, bucket, date.today().isoformat()) if h else None

    @staticmethod
    def update_habit(key: str, **fields: Any) -> dict | None:
        raw = _raw_id(key)
        if raw is None:
            return SqlHabits.update_habit(key, **fields)
        with _DB_LOCK:
            bucket = LifeOSService.get_data_bucket()
            habit = next((h for h in bucket.get("lifeos_habits") or [] if h.get("id") == raw), None)
            if not habit:
                return None
            if fields.get("name") is not None:
                habit["title"] = fields["name"]
            if 'target_value' in fields:
                habit['targetValue'] = fields['target_value']
            if 'unit' in fields:
                habit['unit'] = fields['unit']
            if fields.get("isPriority") is not None:
                habit["isPriority"] = bool(fields["isPriority"])
            options = habit.setdefault("jarvis", {})
            for field in ("category", "routine_block", "frequency_type", "start_time", "day_slots", "days_of_week",
                          "items_list", "time_exceptions", "icon", "color"):
                if field in fields and fields[field] is not None:
                    options[field] = fields[field]
            if not LifeOSService.save_data_bucket(bucket):
                raise OSError("Falha ao atualizar o hábito.")
            return _evolute_row(habit, bucket, date.today().isoformat())

    @staticmethod
    def set_day_slot(key: str, day: Any, slot_data: Any) -> dict | None:
        from app.services.habits import normalize_day
        habit = PersonalHabits.get_habit(key)
        if habit is None:
            return None
        return PersonalHabits.update_habit(key, day_slots={**habit["day_slots"], normalize_day(day): slot_data})

    @staticmethod
    def check_in(key: str, date_str: str = "", value: float = 1, notes: str = "") -> dict:
        if _raw_id(key) is None:
            return SqlHabits.check_in(key, date_str, value, notes)
        return PersonalHabits._set_evolute_check(key, date_str, True, notes)

    @staticmethod
    def uncheck_in(key: str, date_str: str = "") -> dict:
        if _raw_id(key) is None:
            return SqlHabits.uncheck_in(key, date_str)
        return PersonalHabits._set_evolute_check(key, date_str, False, "")

    @staticmethod
    def _set_evolute_check(key: str, day: str, completed: bool, notes: str, value: float | None = None) -> dict:
        raw = _raw_id(key)
        day = day or date.today().isoformat()
        with _DB_LOCK:
            bucket = LifeOSService.get_data_bucket()
            habit = next((h for h in bucket.get("lifeos_habits") or [] if h.get("id") == raw), None)
            if not habit or habit.get("archived"):
                raise ValueError("Hábito indisponível.")
            log = bucket.setdefault(f"lifeos_hlog_{day}", {}).setdefault(raw, {})
            changed = bool(log.get("completed")) != completed
            value_changed = value is not None and value != log.get("currentValue")
            if changed or value_changed:
                log.update(completed=completed, manuallyUnchecked=not completed)
                if value is not None:
                    log["currentValue"] = value
                    log["manuallyUnchecked"] = False
                if changed and completed and day == date.today().isoformat():
                    log["completed_at"] = time.time()
                elif not completed:
                    log.pop("completed_at", None)
                if notes:
                    log["notes"] = notes
                if changed and day == date.today().isoformat():
                    habit["streak"] = max(0, int(habit.get("streak") or 0) + (1 if completed else -1))
                    habit["bestStreak"] = max(habit["streak"], int(habit.get("bestStreak") or 0))
                if not LifeOSService.save_data_bucket(bucket):
                    raise OSError("Falha ao registrar o hábito.")
            return {**_evolute_row(habit, bucket, day), "changed": changed}

    @staticmethod
    def delete_habit(key: str) -> bool:
        raw = _raw_id(key)
        if raw is None:
            return SqlHabits.delete_habit(key)
        with _DB_LOCK:
            bucket = LifeOSService.get_data_bucket()
            before = bucket.get("lifeos_habits") or []
            remaining = [h for h in before if h.get("id") != raw]
            if len(remaining) == len(before):
                return False
            bucket["lifeos_habits"] = remaining
            return LifeOSService.save_data_bucket(bucket)
