"""Tests for the py-fsrs scheduler adapter (app.storage.tutor.fsrs)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.storage.tutor.fsrs import (
    GRADE_AGAIN,
    GRADE_EASY,
    GRADE_GOOD,
    GRADE_HARD,
    apply_review,
    is_due,
    new_card_fields,
    normalize_card,
    parse_when,
    retrievability,
    review_fields,
    validate_grade,
)

NOW = datetime(2026, 6, 1, 15, 0, tzinfo=timezone.utc)


def _new_card() -> dict:
    card = new_card_fields()
    card["due"] = NOW.isoformat()
    return card


def _review(card: dict, grade: int, now: datetime):
    result = apply_review(card, grade, now=now)
    card.update(review_fields(result))
    return result


def _review_card(now: datetime = NOW) -> dict:
    card = _new_card()
    result = _review(card, GRADE_EASY, now)
    assert result.state == "review"
    return card


# ── grade validation ────────────────────────────────────────────

class TestValidateGrade:
    @pytest.mark.parametrize("grade", [5, -1, True, "2", None, 2.0])
    def test_rejects_invalid(self, grade) -> None:
        with pytest.raises(ValueError):
            validate_grade(grade)
        with pytest.raises(ValueError):
            apply_review(_new_card(), grade, now=NOW)

    @pytest.mark.parametrize("grade", [GRADE_AGAIN, GRADE_HARD, GRADE_GOOD, GRADE_EASY])
    def test_accepts_valid(self, grade: int) -> None:
        assert validate_grade(grade) == grade


# ── learning / relearning steps ─────────────────────────────────

class TestLearningSteps:
    def test_new_good_goes_to_second_learning_step(self) -> None:
        r = apply_review(_new_card(), GRADE_GOOD, now=NOW)
        assert r.state == "learning"
        assert r.step == 1
        assert parse_when(r.due) == NOW + timedelta(minutes=10)
        assert r.interval == 0
        assert r.reps == 1
        assert r.lapses == 0

    def test_second_good_graduates(self) -> None:
        card = _new_card()
        first = _review(card, GRADE_GOOD, NOW)
        second = _review(card, GRADE_GOOD, parse_when(first.due))
        assert second.state == "review"
        assert second.step is None
        assert second.interval >= 1
        assert second.reps == 2

    def test_again_on_new_restarts_first_step(self) -> None:
        r = apply_review(_new_card(), GRADE_AGAIN, now=NOW)
        assert r.state == "learning"
        assert r.step == 0
        assert parse_when(r.due) == NOW + timedelta(minutes=1)
        assert r.lapses == 0

    def test_again_on_review_card_relearns(self) -> None:
        card = _review_card()
        due = parse_when(card["due"])
        r = _review(card, GRADE_AGAIN, due)
        assert r.state == "relearning"
        assert r.lapses == 1
        assert parse_when(r.due) == due + timedelta(minutes=10)
        assert r.interval == 0

    def test_intervals_capped_at_365_days(self) -> None:
        card = _new_card()
        now = NOW
        for _ in range(30):
            r = _review(card, GRADE_EASY, now)
            assert r.interval <= 365
            now = parse_when(r.due)
        assert r.interval == 365


# ── retrievability ──────────────────────────────────────────────

class TestRetrievability:
    def test_none_before_first_review(self) -> None:
        assert apply_review(_new_card(), GRADE_GOOD, now=NOW).retrievability is None

    def test_pre_review_value_days_later(self) -> None:
        card = _review_card()
        later = parse_when(card["due"]) + timedelta(days=3)
        r = apply_review(card, GRADE_GOOD, now=later)
        assert r.retrievability is not None
        assert 0.0 < r.retrievability < 1.0
        assert r.retrievability != 1.0

    def test_curve_bounds(self) -> None:
        for elapsed in (0, 1, 5, 30, 180):
            assert 0.0 <= retrievability(10.0, elapsed) <= 1.0

    def test_zero_elapsed_returns_1(self) -> None:
        assert retrievability(5.0, 0) == pytest.approx(1.0)

    def test_decreasing_in_time(self) -> None:
        values = [retrievability(10.0, t) for t in (0, 1, 10, 100, 1000)]
        assert values == sorted(values, reverse=True)
        assert len(set(values)) == len(values)

    def test_target_retention_at_stability(self) -> None:
        assert retrievability(10.0, 10.0) == pytest.approx(0.9)

    def test_zero_stability_returns_0(self) -> None:
        assert retrievability(0.0, 5) == 0.0


# ── lazy migration of stored cards ──────────────────────────────

class TestMigration:
    def test_legacy_sm2_card_keeps_due_day_and_keys(self) -> None:
        card = {"ease": 2.5, "interval": 3, "reps": 2, "lapses": 0, "due": "2026-06-04"}
        normalize_card(card)
        assert card["state"] == "review"
        assert parse_when(card["due"]).astimezone().date() == date(2026, 6, 4)
        assert card["ease"] == 2.5
        assert card["interval"] == 3
        assert card["stability"] == 3.0
        assert card["difficulty"] == 5.0
        assert parse_when(card["last_review"]) == parse_when("2026-06-01")
        r = apply_review(card, GRADE_GOOD, now=parse_when(card["due"]))
        assert r.state == "review"
        assert r.reps == 3
        assert 0.0 < r.retrievability < 1.0

    def test_old_fsrs_lite_unreviewed_card_is_new(self) -> None:
        card = {"difficulty": 5, "stability": 1.0, "reps": 0, "lapses": 0, "due": str(date.today())}
        normalize_card(card)
        assert card["state"] == "new"
        assert card["step"] == 0
        assert card["due"] == str(date.today())
        r = apply_review(card, GRADE_GOOD, now=NOW)
        assert r.state == "learning"

    def test_huge_legacy_stability_is_clamped(self) -> None:
        card = {"stability": 5000, "difficulty": 4, "reps": 6, "lapses": 1, "due": "2026-06-01"}
        normalize_card(card)
        assert card["stability"] == 365.0
        r = apply_review(card, GRADE_EASY, now=NOW)
        assert r.interval <= 365

    def test_normalize_is_idempotent(self) -> None:
        card = {"ease": 2.5, "interval": 3, "reps": 2, "lapses": 0, "due": "2026-06-04"}
        once = dict(normalize_card(card))
        assert normalize_card(card) == once


# ── is_due ──────────────────────────────────────────────────────

class TestIsDue:
    def test_past_due_returns_true(self) -> None:
        yesterday = date.today() - timedelta(days=1)
        assert is_due({"due": str(yesterday)}) is True

    def test_today_due_returns_true(self) -> None:
        assert is_due({"due": str(date.today())}) is True

    def test_future_due_returns_false(self) -> None:
        tomorrow = date.today() + timedelta(days=1)
        assert is_due({"due": str(tomorrow)}) is False

    def test_new_card_is_due(self) -> None:
        assert is_due(_new_card(), now=NOW) is True

    def test_learning_card_due_in_minutes(self) -> None:
        card = {"state": "learning", "step": 1, "stability": 2.0, "difficulty": 5.0,
                "reps": 1, "lapses": 0, "last_review": NOW.isoformat(),
                "due": (NOW + timedelta(minutes=5)).isoformat()}
        assert is_due(card, now=NOW) is False
        assert is_due(card, now=NOW + timedelta(minutes=6)) is True

    def test_review_card_due_later_today_counts(self) -> None:
        local_noon = datetime(2026, 6, 1, 12).astimezone().astimezone(timezone.utc)
        card = {"state": "review", "step": None, "stability": 5.0, "difficulty": 5.0,
                "reps": 3, "lapses": 0, "last_review": (local_noon - timedelta(days=5)).isoformat(),
                "due": (local_noon + timedelta(hours=1)).isoformat()}
        assert is_due(card, now=local_noon) is True
        assert is_due(card, now=local_noon - timedelta(days=1)) is False
