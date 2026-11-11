"""Unified study XP, daily goal and streak shared by the tutor and language decks."""
from __future__ import annotations

import copy
import json
import threading
from datetime import date, timedelta
from pathlib import Path
from typing import Any

XP_REVIEW = 10
XP_PRONUNCIATION = 15
XP_CONVERSATION = 25
XP_SHADOWING = 20
XP_POMODORO = 20
DEFAULT_DAILY_GOAL = 100
POMODORO_MIN_MINUTES = 5
POMODORO_MAX_MINUTES = 90

LEVEL_NAMES = [
    "Iniciante", "Aprendiz", "Estudante", "Dedicado", "Focado",
    "Avançado", "Expert", "Mestre", "Sábio", "Lenda",
]

DEFAULT_XP_DATA: dict[str, Any] = {
    "schema_version": 1,
    "daily": {},
    "daily_goal": DEFAULT_DAILY_GOAL,
    "legacy_total": 0,
    "counters": {"pomodoros": 0},
    "legacy_streak": {"count": 0, "last_date": None},
    "imported_sources": [],
}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_day(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10]) if value else None
    except ValueError:
        return None


class StudyXP:
    """XP per local day in ``<dir>/xp.json``. Reads never write; only mutations persist."""

    def __init__(self, storage_dir: str | Path) -> None:
        self.storage_dir = Path(storage_dir)
        self.path = self.storage_dir / "xp.json"
        self._lock = threading.Lock()
        self._data: dict[str, Any] | None = None

    # ── Persistence ───────────────────────────────────────────────

    def _loaded(self) -> dict[str, Any]:
        if self._data is None:
            data = copy.deepcopy(DEFAULT_XP_DATA)
            try:
                stored = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(stored, dict):
                    data.update(stored)
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass
            self._data = data
        return self._data

    def _save(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _total(self, data: dict[str, Any]) -> int:
        return _int(data.get("legacy_total")) + sum(_int(v) for v in data["daily"].values())

    # ── Mutations ─────────────────────────────────────────────────

    def add(self, amount: int, source: str = "", day: date | str | None = None) -> int:
        """Add XP to ``day`` (default today); ``source`` names the caller (tutor, language, pomodoro)."""
        with self._lock:
            data = self._loaded()
            amount = _int(amount)
            if amount > 0:
                key = str(day or date.today())
                data["daily"][key] = _int(data["daily"].get(key)) + amount
                self._save()
            return self._total(data)

    def revoke(self, amount: int, day: date | str | None = None) -> int:
        with self._lock:
            data = self._loaded()
            amount = _int(amount)
            key = str(day or date.today())
            if amount > 0 and key in data["daily"]:
                remaining = max(0, _int(data["daily"][key]) - amount)
                if remaining:
                    data["daily"][key] = remaining
                else:
                    data["daily"].pop(key)
                self._save()
            return self._total(data)

    def set_daily_goal(self, xp: int) -> int:
        with self._lock:
            data = self._loaded()
            data["daily_goal"] = max(10, min(500, _int(xp, DEFAULT_DAILY_GOAL)))
            self._save()
            return data["daily_goal"]

    def count_pomodoro(self) -> int:
        with self._lock:
            data = self._loaded()
            counters = data.setdefault("counters", {})
            counters["pomodoros"] = _int(counters.get("pomodoros")) + 1
            self._save()
            return counters["pomodoros"]

    def import_legacy(
        self,
        source: str,
        total_xp: Any = 0,
        daily_xp: Any = 0,
        last_study_date: Any = None,
        streak_count: Any = 0,
        daily_goal: Any = None,
    ) -> None:
        """Merge a deck's old XP fields once (in memory; persisted with the next mutation)."""
        with self._lock:
            data = self._loaded()
            if source in data["imported_sources"]:
                return
            total_xp = max(0, _int(total_xp))
            daily_xp = max(0, _int(daily_xp))
            last_day = _parse_day(last_study_date)
            if last_day and daily_xp:
                key = str(last_day)
                data["daily"][key] = _int(data["daily"].get(key)) + daily_xp
            data["legacy_total"] = _int(data.get("legacy_total")) + max(0, total_xp - (daily_xp if last_day else 0))
            count = max(0, _int(streak_count))
            current = data.get("legacy_streak") or {}
            current_day = _parse_day(current.get("last_date"))
            if last_day and count and (
                current_day is None
                or last_day > current_day
                or (last_day == current_day and count > _int(current.get("count")))
            ):
                data["legacy_streak"] = {"count": count, "last_date": str(last_day)}
            if daily_goal is not None:
                data["daily_goal"] = max(_int(data.get("daily_goal"), DEFAULT_DAILY_GOAL), _int(daily_goal))
            data["imported_sources"].append(source)

    # ── Reads ─────────────────────────────────────────────────────

    def daily_totals(self) -> dict[str, int]:
        with self._lock:
            return {k: _int(v) for k, v in self._loaded()["daily"].items()}

    def _active_days(self, data: dict[str, Any]) -> set[date]:
        days = {d for k, v in data["daily"].items() if _int(v) > 0 and (d := _parse_day(k))}
        legacy = data.get("legacy_streak") or {}
        last = _parse_day(legacy.get("last_date"))
        if last:
            days.update(last - timedelta(days=i) for i in range(max(0, _int(legacy.get("count")))))
        return days

    def summary(self, today: date | None = None) -> dict[str, Any]:
        today = today or date.today()
        with self._lock:
            data = self._loaded()
            active = self._active_days(data)
            daily_xp = _int(data["daily"].get(str(today)))
            daily_goal = _int(data.get("daily_goal"), DEFAULT_DAILY_GOAL)
            pomodoros = _int((data.get("counters") or {}).get("pomodoros"))
            total = self._total(data)

        anchor = today if today in active else today - timedelta(days=1)
        streak = 0
        while anchor - timedelta(days=streak) in active:
            streak += 1

        best = run = 0
        previous: date | None = None
        for day in sorted(active):
            run = run + 1 if previous and day - previous == timedelta(days=1) else 1
            best = max(best, run)
            previous = day
        past = [d for d in active if d <= today]

        return {
            "total_xp": total,
            "daily_xp": daily_xp,
            "daily_goal": daily_goal,
            "goal_met": daily_xp >= daily_goal,
            "studied_today": today in active,
            "streak": streak,
            "best_streak": best,
            "pomodoros": pomodoros,
            "last_study_date": str(max(past)) if past else None,
        }


def _threshold(level: int) -> int:
    return 50 * level * (level - 1)


def level_for(total: int) -> dict[str, Any]:
    total = max(0, _int(total))
    level = 1
    while _threshold(level + 1) <= total:
        level += 1
    name = LEVEL_NAMES[level - 1] if level <= len(LEVEL_NAMES) else f"Lenda {level - len(LEVEL_NAMES) + 1}"
    return {
        "level": level,
        "name": name,
        "xp_into_level": total - _threshold(level),
        "xp_for_next": _threshold(level + 1) - _threshold(level),
        "next_threshold": _threshold(level + 1),
    }


def badges(total_reviews: int, best_streak: int, total_xp: int, pomodoros: int, vocab_count: int) -> list[dict[str, Any]]:
    rules = [
        ("first_review", "Primeira revisão", "Faça sua primeira revisão.", total_reviews >= 1),
        ("reviews_100", "100 revisões", "Complete 100 revisões.", total_reviews >= 100),
        ("streak_7", "Sequência de 7 dias", "Estude 7 dias seguidos.", best_streak >= 7),
        ("streak_30", "Sequência de 30 dias", "Estude 30 dias seguidos.", best_streak >= 30),
        ("xp_1000", "1.000 XP", "Acumule 1.000 XP.", total_xp >= 1000),
        ("pomodoro_10", "10 Pomodoros", "Conclua 10 Pomodoros.", pomodoros >= 10),
        ("vocab_50", "50 palavras", "Tenha 50 palavras no vocabulário.", vocab_count >= 50),
    ]
    return [
        {"id": badge_id, "label": label, "description": description, "earned": bool(earned)}
        for badge_id, label, description, earned in rules
    ]


_INSTANCES: dict[Path, StudyXP] = {}
_INSTANCES_LOCK = threading.Lock()


def get_study_xp(path: str | Path) -> StudyXP:
    """One shared StudyXP per directory."""
    key = Path(path).resolve()
    with _INSTANCES_LOCK:
        if key not in _INSTANCES:
            _INSTANCES[key] = StudyXP(key)
        return _INSTANCES[key]
