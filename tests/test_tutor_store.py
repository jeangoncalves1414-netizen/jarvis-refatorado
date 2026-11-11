from datetime import date, datetime, timedelta, timezone
import uuid

import pytest

from app.storage.tutor.fsrs import parse_when
from app.storage.tutor_store import TutorStore


def _store_dir(tmp_path) -> str:
    return str(tmp_path / f"tutor-{uuid.uuid4().hex}")


def test_add_and_review_flashcard(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    card_id = store.add_flashcard("2+2?", "4", topic="aritmética")
    assert card_id.startswith("fc-")
    assert len(store.get_due_flashcards()) == 1

    reviewed = store.review_flashcard(card_id, 3)
    assert reviewed is not None
    assert reviewed["reps"] == 1
    assert reviewed["state"] == "review"
    assert parse_when(reviewed["due"]).astimezone().date() > date.today()
    assert store.get_due_flashcards() == []


def test_good_on_new_flashcard_stays_in_learning_today(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    card_id = store.add_flashcard("3+3?", "6")

    reviewed = store.review_flashcard(card_id, 2)
    assert reviewed is not None
    assert reviewed["state"] == "learning"
    due = parse_when(reviewed["due"])
    assert due > datetime.now(timezone.utc)
    assert due - datetime.now(timezone.utc) <= timedelta(minutes=10)
    assert store.get_due_flashcards() == []


def test_review_awards_xp(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    card_id = store.add_flashcard("4+4?", "8")
    store.review_flashcard(card_id, 2)
    summary = store.xp.summary()
    assert summary["total_xp"] == 10
    assert summary["daily_xp"] == 10
    assert summary["streak"] == 1
    assert store.get_streak_info()["total_xp"] == 10


def test_invalid_grade_raises(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    card_id = store.add_flashcard("Q", "A")
    for grade in (5, -1, True, "2", None):
        with pytest.raises(ValueError):
            store.review_flashcard(card_id, grade)
    assert store.get_flashcards()[0]["reps"] == 0


def test_feynman_attempt_adds_weak_spot_on_low_grade(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    store.add_feynman_attempt("logaritmos", "explicação curta", grade=1)
    progress = store.get_progress()
    assert progress["stats"]["feynman_attempts"] == 1
    assert "logaritmos" in progress["weak_spots"]


def test_assessment_recorded(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    aid = store.add_assessment("04-matematica", correct=4, total=5, weak_topics=["geometria"])
    assert aid.startswith("as-")
    assessments = store.get_assessments()
    assert assessments[0]["score"] == 0.8
    assert store.get_progress()["stats"]["quizzes_taken"] == 1


def test_dashboard_structure(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    store.add_flashcard("Q", "A")
    dash = store.get_dashboard()
    assert "progress" in dash
    assert dash["due_flashcards"] == 1
    assert "stages" in dash["progress"]
