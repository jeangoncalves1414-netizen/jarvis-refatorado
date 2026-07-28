from datetime import date
import uuid

from app.storage.tutor_store import TutorStore


def _store_dir(tmp_path) -> str:
    return str(tmp_path / f"tutor-{uuid.uuid4().hex}")


def test_add_and_review_flashcard(tmp_path) -> None:
    store = TutorStore(storage_dir=_store_dir(tmp_path))
    card_id = store.add_flashcard("2+2?", "4", topic="aritmética")
    assert card_id.startswith("fc-")
    assert len(store.get_due_flashcards()) == 1

    reviewed = store.review_flashcard(card_id, 2)
    assert reviewed is not None
    assert reviewed["reps"] == 1
    assert reviewed["due"] > str(date.today())


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
