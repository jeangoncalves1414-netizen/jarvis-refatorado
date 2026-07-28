from datetime import date

from app.storage.tutor.srs import GRADE_AGAIN, GRADE_EASY, GRADE_GOOD, apply_review, is_due


def test_apply_review_again_resets_and_schedules_tomorrow() -> None:
    card = {"ease": 2.3, "reps": 3, "lapses": 0, "interval": 10}
    result = apply_review(card, GRADE_AGAIN, date(2026, 7, 6))
    assert result.reps == 0
    assert result.lapses == 1
    assert result.interval == 0
    assert result.due == "2026-07-07"


def test_apply_review_good_first_interval() -> None:
    card = {"ease": 2.3, "reps": 0, "lapses": 0, "interval": 0}
    result = apply_review(card, GRADE_GOOD, date(2026, 7, 6))
    assert result.reps == 1
    assert result.interval == 1
    assert result.due == "2026-07-07"


def test_apply_review_good_second_interval() -> None:
    card = {"ease": 2.3, "reps": 1, "lapses": 0, "interval": 1}
    result = apply_review(card, GRADE_GOOD, date(2026, 7, 6))
    assert result.reps == 2
    assert result.interval == 3
    assert result.due == "2026-07-09"


def test_apply_review_easy_minimum_interval() -> None:
    card = {"ease": 2.3, "reps": 2, "lapses": 0, "interval": 3}
    result = apply_review(card, GRADE_EASY, date(2026, 7, 6))
    assert result.interval >= 4
    assert result.ease > 2.3


def test_is_due() -> None:
    assert is_due({"due": "2026-07-05"}, date(2026, 7, 6))
    assert not is_due({"due": "2026-07-10"}, date(2026, 7, 6))
