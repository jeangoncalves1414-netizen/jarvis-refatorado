"""Spaced repetition scheduler shared by tutor flashcards and language vocabulary.

Thin adapter over py-fsrs (https://github.com/open-spaced-repetition/py-fsrs):
cards are stored as plain dicts in the JSON stores and converted to
``fsrs.Card`` objects only while scheduling. Legacy cards (SM-2 shape or the
old hand-tuned "FSRS-lite" shape) are migrated lazily by ``normalize_card``
without dropping any existing keys.

Grades keep the app convention 0..3 (Again, Hard, Good, Easy) and map to
``fsrs.Rating`` 1..4.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import fsrs

GRADE_AGAIN = 0
GRADE_HARD = 1
GRADE_GOOD = 2
GRADE_EASY = 3

MAX_INTERVAL_DAYS = 365

SCHEDULER = fsrs.Scheduler(
    desired_retention=0.9,
    learning_steps=(timedelta(minutes=1), timedelta(minutes=10)),
    relearning_steps=(timedelta(minutes=10),),
    maximum_interval=MAX_INTERVAL_DAYS,
    enable_fuzzing=False,
)

SCHEDULING_KEYS = (
    "state",
    "step",
    "stability",
    "difficulty",
    "due",
    "last_review",
    "interval",
    "ease",
    "reps",
    "lapses",
    "retrievability",
)

_STATE_TO_FSRS = {
    "learning": fsrs.State.Learning,
    "review": fsrs.State.Review,
    "relearning": fsrs.State.Relearning,
}
_FSRS_TO_STATE = {value: key for key, value in _STATE_TO_FSRS.items()}


@dataclass
class ReviewResult:
    interval: int  # whole days until due, 0 when due later today
    ease: float  # kept for backward compat; derived from difficulty
    reps: int
    lapses: int
    due: str  # ISO datetime, UTC
    difficulty: float
    stability: float
    retrievability: float | None  # recall probability BEFORE this review
    state: str  # learning | review | relearning
    step: int | None
    last_review: str  # ISO datetime, UTC


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def validate_grade(grade: Any) -> int:
    if isinstance(grade, bool) or not isinstance(grade, int) or grade not in (0, 1, 2, 3):
        raise ValueError("invalid_grade")
    return grade


def _is_date_only(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _local_midnight_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day).astimezone().astimezone(timezone.utc)


def parse_when(value: Any) -> datetime | None:
    """Parse a stored due/last_review value into an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        return _local_midnight_utc(value)
    elif _is_date_only(value):
        return _local_midnight_utc(date.fromisoformat(value))
    else:
        try:
            parsed = datetime.fromisoformat(str(value))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.astimezone()
    return parsed.astimezone(timezone.utc)


def _resolve_now(now: datetime | None, today: date | None) -> datetime:
    if now is not None:
        return parse_when(now) or datetime.now(timezone.utc)
    if today is not None:
        return datetime.combine(today, time(12)).astimezone().astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def normalize_card(card: dict[str, Any]) -> dict[str, Any]:
    """Lazily migrate a stored card to the scheduler shape (in place, never deletes keys)."""
    if "state" not in card:
        reps = int(card.get("reps") or 0)
        lapses = int(card.get("lapses") or 0)
        if reps == 0 and lapses == 0 and not card.get("last_review"):
            card["state"] = "new"
            card["step"] = 0
        else:
            interval = int(card.get("interval") or 0)
            due = parse_when(card.get("due")) or datetime.now(timezone.utc)
            last_review = parse_when(card.get("last_review")) or (due - timedelta(days=max(1, interval)))
            card["state"] = "review"
            card["step"] = None
            card["stability"] = _clamp(0.1, float(MAX_INTERVAL_DAYS), float(card.get("stability") or interval or 1))
            card["difficulty"] = _clamp(1.0, 10.0, float(card.get("difficulty") or 5))
            card["last_review"] = last_review.isoformat()
            card["due"] = due.isoformat()
    card.setdefault("reps", 0)
    card.setdefault("lapses", 0)
    if card.get("state") == "new":
        card.setdefault("due", datetime.now(timezone.utc).isoformat())
    return card


def new_card_fields() -> dict[str, Any]:
    """Scheduling fields of a freshly created card."""
    return {
        "state": "new",
        "step": 0,
        "stability": None,
        "difficulty": None,
        "reps": 0,
        "lapses": 0,
        "due": datetime.now(timezone.utc).isoformat(),
    }


def review_fields(result: ReviewResult) -> dict[str, Any]:
    """Card fields to write back after ``apply_review``."""
    return {
        "interval": result.interval,
        "ease": result.ease,
        "reps": result.reps,
        "lapses": result.lapses,
        "due": result.due,
        "difficulty": result.difficulty,
        "stability": result.stability,
        "retrievability": result.retrievability,
        "state": result.state,
        "step": result.step,
        "last_review": result.last_review,
    }


def to_fsrs(card: dict[str, Any]) -> fsrs.Card:
    state = card.get("state", "new")
    if state not in _STATE_TO_FSRS:
        return fsrs.Card(card_id=1, state=fsrs.State.Learning, step=0)
    step = card.get("step")
    stability = card.get("stability")
    difficulty = card.get("difficulty")
    return fsrs.Card(
        card_id=1,
        state=_STATE_TO_FSRS[state],
        step=None if state == "review" else int(step or 0),
        stability=None if stability is None else float(stability),
        difficulty=None if difficulty is None else float(difficulty),
        due=parse_when(card.get("due")),
        last_review=parse_when(card.get("last_review")),
    )


def apply_review(
    card: dict[str, Any],
    grade: int,
    now: datetime | None = None,
    today: date | None = None,
) -> ReviewResult:
    """Schedule the next review of ``card`` (not mutated) for ``grade`` 0..3."""
    grade = validate_grade(grade)
    now = _resolve_now(now, today)
    current = normalize_card(dict(card))
    state_before = current["state"]
    fsrs_card = to_fsrs(current)

    retrievability_before = (
        float(SCHEDULER.get_card_retrievability(fsrs_card, now)) if fsrs_card.last_review else None
    )
    new_card, _ = SCHEDULER.review_card(fsrs_card, fsrs.Rating(grade + 1), review_datetime=now)

    lapses = int(current.get("lapses") or 0)
    if state_before == "review" and grade == GRADE_AGAIN:
        lapses += 1
    difficulty = float(new_card.difficulty)
    return ReviewResult(
        interval=max(0, (new_card.due - now).days),
        ease=round(_clamp(1.3, 2.8, 2.8 - (difficulty - 1) * 0.167), 2),
        reps=int(current.get("reps") or 0) + 1,
        lapses=lapses,
        due=new_card.due.isoformat(),
        difficulty=difficulty,
        stability=float(new_card.stability),
        retrievability=None if retrievability_before is None else round(retrievability_before, 4),
        state=_FSRS_TO_STATE[new_card.state],
        step=new_card.step,
        last_review=now.isoformat(),
    )


def is_due(card: dict[str, Any], now: datetime | None = None, today: date | None = None) -> bool:
    now = _resolve_now(now, today)
    today = today or now.astimezone().date()
    raw_due = card.get("due")
    if _is_date_only(raw_due):
        return raw_due <= str(today)
    current = normalize_card(dict(card))
    state = current.get("state")
    due = parse_when(current.get("due"))
    if state == "new" or due is None:
        return True
    if state in ("learning", "relearning"):
        return due <= now
    return due.astimezone().date() <= today


def retrievability(stability: float, days_elapsed: float) -> float:
    """Probability of recall after ``days_elapsed`` days (FSRS-6 power curve)."""
    if stability <= 0:
        return 0.0
    decay = -SCHEDULER.parameters[20]
    factor = 0.9 ** (1 / decay) - 1
    return (1 + factor * max(0.0, days_elapsed) / stability) ** decay


_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc)


def sort_due(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Learning/relearning first (by due), then review (by due), then new cards in stored order."""
    def key(item: tuple[int, dict[str, Any]]) -> tuple[int, datetime, int]:
        index, card = item
        current = normalize_card(dict(card))
        state = current.get("state")
        due = parse_when(current.get("due")) or _MIN_UTC
        if state in ("learning", "relearning"):
            return (0, due, index)
        if state == "review":
            return (1, due, index)
        return (2, _MIN_UTC, index)

    return [card for _, card in sorted(enumerate(cards), key=key)]


def next_learning_due(cards: list[dict[str, Any]], now: datetime | None = None) -> str | None:
    """Earliest future due (ISO UTC) of learning/relearning cards due later today, else None."""
    now = _resolve_now(now, None)
    today = now.astimezone().date()
    upcoming = []
    for card in cards:
        current = normalize_card(dict(card))
        if current.get("state") not in ("learning", "relearning"):
            continue
        due = parse_when(current.get("due"))
        if due is not None and due > now and due.astimezone().date() == today:
            upcoming.append(due)
    return min(upcoming).isoformat() if upcoming else None
