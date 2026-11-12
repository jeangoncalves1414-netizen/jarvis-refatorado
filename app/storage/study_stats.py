"""Study panel dashboard and statistics built from both decks' review logs and the XP service."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any

from app.storage.study_xp import badges, level_for
from app.storage.tutor.fsrs import next_learning_due, normalize_card

HEATMAP_DAYS = 371
DAILY_REVIEW_DAYS = 30
RETENTION_WINDOW_DAYS = 30
STATES = ("new", "learning", "review", "relearning")


def _active_reviews(tutor: Any, language: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return tutor.review_log.active_reviews(), language.review_log.active_reviews()


def _state_counts(cards: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(normalize_card(dict(card)).get("state") for card in cards)
    return {state: counts.get(state, 0) for state in STATES}


def build_dashboard(tutor: Any, language: Any, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    today = now.astimezone().date()
    upcoming = [
        due for due in (
            next_learning_due(tutor.get_flashcards(), now),
            next_learning_due(language.get_vocabulary(), now),
        ) if due
    ]
    xp = tutor.xp.summary(today)
    tutor_reviews, language_reviews = _active_reviews(tutor, language)
    return {
        "today": str(today),
        "due": {
            "flashcards": len(tutor.get_due_flashcards()),
            "vocabulary": len(language.get_due_vocabulary()),
            "next_due_at": min(upcoming) if upcoming else None,
        },
        "xp": xp,
        "level": level_for(xp["total_xp"]),
        "badges": badges(
            total_reviews=len(tutor_reviews) + len(language_reviews),
            best_streak=xp["best_streak"],
            total_xp=xp["total_xp"],
            pomodoros=xp["pomodoros"],
            vocab_count=len(language.get_vocabulary()),
        ),
    }


def build_stats(tutor: Any, language: Any, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    tutor_reviews, language_reviews = _active_reviews(tutor, language)
    tutor_by_day = Counter(str(r.get("local_date")) for r in tutor_reviews)
    language_by_day = Counter(str(r.get("local_date")) for r in language_reviews)
    xp_by_day = tutor.xp.daily_totals()

    def days(count: int) -> list[str]:
        return [str(today - timedelta(days=offset)) for offset in range(count - 1, -1, -1)]

    window_start = str(today - timedelta(days=RETENTION_WINDOW_DAYS - 1))
    mature = [
        r for r in tutor_reviews + language_reviews
        if r.get("state_before") == "review" and window_start <= str(r.get("local_date")) <= str(today)
    ]
    correct = sum(1 for r in mature if int(r.get("grade") or 0) >= 1)

    flashcards = tutor.get_flashcards()
    vocabulary = language.get_vocabulary()
    tutor_states = _state_counts(flashcards)
    language_states = _state_counts(vocabulary)
    xp = tutor.xp.summary(today)

    return {
        "heatmap": [
            {"date": day, "reviews": tutor_by_day[day] + language_by_day[day], "xp": xp_by_day.get(day, 0)}
            for day in days(HEATMAP_DAYS)
        ],
        "daily_reviews": [
            {"date": day, "tutor": tutor_by_day[day], "language": language_by_day[day]}
            for day in days(DAILY_REVIEW_DAYS)
        ],
        "retention": {
            "rate": round(correct / len(mature), 4) if mature else None,
            "correct": correct,
            "total": len(mature),
            "window_days": RETENTION_WINDOW_DAYS,
        },
        "states": {
            "tutor": tutor_states,
            "language": language_states,
            "total": {state: tutor_states[state] + language_states[state] for state in STATES},
        },
        "totals": {
            "reviews": len(tutor_reviews) + len(language_reviews),
            "pomodoros": xp["pomodoros"],
            "vocabulary": len(vocabulary),
            "flashcards": len(flashcards),
        },
    }
