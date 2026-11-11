"""FSRS (Free Spaced Repetition Scheduler) — lightweight implementation.

Replaces the SM-2 lite algorithm with the DSR (Difficulty-Stability-Retrievability)
model for 20-30% fewer reviews at the same retention level.

Reference: https://github.com/open-spaced-repetition/py-fsrs
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

GRADE_AGAIN = 0
GRADE_HARD = 1
GRADE_GOOD = 2
GRADE_EASY = 3

DEFAULT_DIFFICULTY = 5.0
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0
DEFAULT_STABILITY = 1.0
TARGET_RETENTION = 0.9  # 90% default


@dataclass
class ReviewResult:
    interval: int
    ease: float  # kept for backward compat; maps to difficulty
    reps: int
    lapses: int
    due: str
    difficulty: float
    stability: float
    retrievability: float


def _clamp(lo: float, hi: float, value: float) -> float:
    return max(lo, min(hi, value))


def retrievability(stability: float, days_elapsed: float) -> float:
    """Probability of recall: R = e^(-t/S)."""
    if stability <= 0:
        return 0.0
    return math.exp(-days_elapsed / stability)


def next_interval(stability: float, target_retention: float = TARGET_RETENTION) -> int:
    """Days until R drops to target_retention: t = -S * ln(R)."""
    if stability <= 0 or target_retention <= 0 or target_retention >= 1:
        return 1
    return max(1, round(-stability * math.log(target_retention)))


def apply_review(card: dict[str, Any], grade: int, today: date | None = None) -> ReviewResult:
    """FSRS-lite: update card state after a review.

    Backward compatible with SM-2 card dicts (ease, interval, reps, lapses, due).
    Adds difficulty, stability, retrievability fields.
    """
    today = today or date.today()

    # Read existing state (supports both old SM-2 and new FSRS cards)
    difficulty = float(card.get("difficulty", DEFAULT_DIFFICULTY))
    stability = float(card.get("stability", card.get("interval", DEFAULT_STABILITY) or DEFAULT_STABILITY))
    reps = int(card.get("reps", 0))
    lapses = int(card.get("lapses", 0))

    # Calculate elapsed days since last review
    last_due = card.get("due") or str(today)
    try:
        due_date = date.fromisoformat(last_due)
        elapsed = max(0, (today - due_date).days)
    except (ValueError, TypeError):
        elapsed = 0

    # Current retrievability before this review
    r = retrievability(stability, elapsed) if reps > 0 else 0.0

    # Update difficulty based on grade
    # grade 3 (Easy) → difficulty decreases; grade 0 (Again) → difficulty increases
    difficulty += (3 - grade) * 0.4
    difficulty = _clamp(MIN_DIFFICULTY, MAX_DIFFICULTY, difficulty)

    if grade == GRADE_AGAIN:
        # Lapse: reset stability, increment lapses
        lapses += 1
        reps = 0
        # Stability drops significantly but not to zero
        stability = max(0.5, stability * 0.2)
        interval = 1
        due = today + timedelta(days=1)
    elif grade == GRADE_HARD:
        reps += 1
        hard_factor = 0.8
        if reps <= 1:
            stability = 1.0
        elif reps == 2:
            stability = max(1, stability * 1.5)
        else:
            # Grow stability but with penalty
            stability = stability * (1.0 + (11 - difficulty) * 0.04) * hard_factor
        interval = next_interval(stability)
        due = today + timedelta(days=interval)
    elif grade == GRADE_GOOD:
        reps += 1
        if reps <= 1:
            stability = 1.0
        elif reps == 2:
            stability = 3.0
        else:
            stability = stability * (1.0 + (11 - difficulty) * 0.06)
        interval = next_interval(stability)
        due = today + timedelta(days=interval)
    else:  # EASY
        reps += 1
        easy_bonus = 1.3
        if reps <= 1:
            stability = 4.0
        elif reps == 2:
            stability = max(4, stability * 2.5)
        else:
            stability = stability * (1.0 + (11 - difficulty) * 0.06) * easy_bonus
        interval = next_interval(stability)
        due = today + timedelta(days=interval)

    # Map difficulty back to ease for backward compat (1.3-2.8 range)
    ease = _clamp(1.3, 2.8, 2.8 - (difficulty - 1) * 0.167)

    return ReviewResult(
        interval=interval,
        ease=round(ease, 2),
        reps=reps,
        lapses=lapses,
        due=str(due),
        difficulty=round(difficulty, 2),
        stability=round(stability, 2),
        retrievability=round(retrievability(stability, 0), 4),
    )


def is_due(card: dict[str, Any], today: date | None = None) -> bool:
    today = today or date.today()
    due = card.get("due") or str(today)
    try:
        return due <= str(today)
    except TypeError:
        return True

