from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any


GRADE_AGAIN = 0
GRADE_HARD = 1
GRADE_GOOD = 2
GRADE_EASY = 3

DEFAULT_EASE = 2.3
MIN_EASE = 1.3
MAX_EASE = 2.8


@dataclass
class ReviewResult:
    interval: int
    ease: float
    reps: int
    lapses: int
    due: str


def apply_review(card: dict[str, Any], grade: int, today: date | None = None) -> ReviewResult:
    """SM-2-lite from learn-anything-tutor (§6)."""
    today = today or date.today()
    ease = float(card.get("ease", DEFAULT_EASE))
    reps = int(card.get("reps", 0))
    lapses = int(card.get("lapses", 0))
    interval = int(card.get("interval", 0))

    if grade == GRADE_AGAIN:
        reps = 0
        lapses += 1
        interval = 0
        ease = max(MIN_EASE, ease - 0.20)
        due = today + timedelta(days=1)
    elif grade == GRADE_HARD:
        interval = max(1, round(interval * 1.2)) if interval else 1
        ease = max(MIN_EASE, ease - 0.15)
        reps += 1
        due = today + timedelta(days=interval)
    elif grade == GRADE_GOOD:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = max(1, round(interval * ease))
        reps += 1
        due = today + timedelta(days=interval)
    else:  # EASY
        interval = max(4, round(interval * ease * 1.3)) if interval else 4
        ease = min(MAX_EASE, ease + 0.15)
        reps += 1
        due = today + timedelta(days=interval)

    ease = max(MIN_EASE, min(MAX_EASE, ease))
    return ReviewResult(
        interval=interval,
        ease=round(ease, 2),
        reps=reps,
        lapses=lapses,
        due=str(due),
    )


def is_due(card: dict[str, Any], today: date | None = None) -> bool:
    today = today or date.today()
    due = card.get("due") or str(today)
    try:
        return due <= str(today)
    except TypeError:
        return True
