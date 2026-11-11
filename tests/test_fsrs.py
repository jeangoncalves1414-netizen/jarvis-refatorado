"""Tests for FSRS (Free Spaced Repetition Scheduler) algorithm."""
from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from app.storage.tutor.fsrs import (
    GRADE_AGAIN,
    GRADE_EASY,
    GRADE_GOOD,
    GRADE_HARD,
    apply_review,
    is_due,
    retrievability,
)


# ── helpers ──────────────────────────────────────────────────────

def _new_card(*, due: str | None = None) -> dict:
    """Minimal fresh card dict."""
    return {
        "reps": 0,
        "lapses": 0,
        "difficulty": 5.0,
        "stability": 1.0,
        "due": due or str(date.today()),
    }


def _reviewed_card(grade: int = GRADE_GOOD, n: int = 3, today: date | None = None) -> dict:
    """Build a card that has been reviewed *n* times with *grade*."""
    today = today or date.today()
    card = _new_card(due=str(today))
    for _ in range(n):
        r = apply_review(card, grade, today=today)
        card.update(
            reps=r.reps,
            lapses=r.lapses,
            difficulty=r.difficulty,
            stability=r.stability,
            due=r.due,
        )
        today = date.fromisoformat(r.due)
    return card


# ── apply_review — all four grades ──────────────────────────────

class TestApplyReviewGrades:
    """apply_review must handle grades 0-3 and return valid ReviewResult."""

    @pytest.fixture()
    def today(self) -> date:
        return date(2026, 6, 1)

    @pytest.fixture()
    def card(self, today: date) -> dict:
        return _new_card(due=str(today))

    def test_grade_again(self, card: dict, today: date) -> None:
        r = apply_review(card, GRADE_AGAIN, today=today)
        assert r.interval == 1
        assert r.reps == 0
        assert r.lapses == 1
        assert r.due == str(today + timedelta(days=1))

    def test_grade_hard(self, card: dict, today: date) -> None:
        r = apply_review(card, GRADE_HARD, today=today)
        assert r.interval >= 1
        assert r.reps == 1
        assert r.lapses == 0

    def test_grade_good(self, card: dict, today: date) -> None:
        r = apply_review(card, GRADE_GOOD, today=today)
        assert r.interval >= 1
        assert r.reps == 1
        assert r.lapses == 0

    def test_grade_easy(self, card: dict, today: date) -> None:
        r = apply_review(card, GRADE_EASY, today=today)
        assert r.interval >= 1
        assert r.reps == 1
        assert r.lapses == 0


# ── Stability dynamics ──────────────────────────────────────────

class TestStabilityDynamics:
    """Stability must change appropriately per grade."""

    @pytest.fixture()
    def today(self) -> date:
        return date(2026, 6, 1)

    def test_again_stability_decreases_or_resets(self, today: date) -> None:
        card = _reviewed_card(GRADE_GOOD, n=3, today=today)
        old_stability = card["stability"]
        r = apply_review(card, GRADE_AGAIN, today=date.fromisoformat(card["due"]))
        assert r.stability < old_stability

    def test_easy_stability_exceeds_good(self, today: date) -> None:
        card_good = _new_card(due=str(today))
        card_easy = _new_card(due=str(today))

        r_good = apply_review(card_good, GRADE_GOOD, today=today)
        r_easy = apply_review(card_easy, GRADE_EASY, today=today)
        assert r_easy.stability > r_good.stability


# ── is_due ──────────────────────────────────────────────────────

class TestIsDue:
    def test_past_due_returns_true(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        card = {"due": str(yesterday)}
        assert is_due(card) is True

    def test_today_due_returns_true(self) -> None:
        card = {"due": str(date.today())}
        assert is_due(card) is True

    def test_future_due_returns_false(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        card = {"due": str(tomorrow)}
        assert is_due(card) is False


# ── retrievability ──────────────────────────────────────────────

class TestRetrievability:
    def test_returns_between_0_and_1(self) -> None:
        for elapsed in (0, 1, 5, 30, 180):
            r = retrievability(10.0, elapsed)
            assert 0.0 <= r <= 1.0

    def test_zero_elapsed_returns_1(self) -> None:
        assert retrievability(5.0, 0) == pytest.approx(1.0)

    def test_large_elapsed_approaches_0(self) -> None:
        r = retrievability(1.0, 1000)
        assert r < 0.01

    def test_zero_stability_returns_0(self) -> None:
        assert retrievability(0.0, 5) == 0.0


# ── Backward compatibility (SM-2 card without FSRS fields) ─────

class TestBackwardCompatibility:
    def test_card_without_difficulty_stability(self) -> None:
        old_card: dict = {
            "ease": 2.5,
            "interval": 3,
            "reps": 2,
            "lapses": 0,
            "due": str(date.today()),
        }
        r = apply_review(old_card, GRADE_GOOD)
        assert r.reps == 3
        assert r.difficulty > 0
        assert r.stability > 0
        assert r.due > str(date.today())

    def test_completely_empty_card(self) -> None:
        r = apply_review({}, GRADE_GOOD)
        assert r.reps == 1
        assert r.stability >= 1.0
