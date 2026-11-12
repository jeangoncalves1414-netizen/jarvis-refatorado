import copy

import pytest

from app.storage.language_store import LanguageStore
from app.storage.tutor_store import TutorStore


@pytest.mark.parametrize("kind", ["tutor", "language"])
def test_undo_resurrects_deleted_card_with_content_and_schedule(tmp_path, kind):
    store = TutorStore(str(tmp_path)) if kind == "tutor" else LanguageStore(str(tmp_path))
    field = "flashcards" if kind == "tutor" else "vocabulary"
    add = store.add_flashcard if kind == "tutor" else store.add_vocabulary
    review = store.review_flashcard if kind == "tutor" else store.review_vocabulary
    identifier = add("hello", "olá")
    before = copy.deepcopy(store._data[field][0])
    review(identifier, 3)
    store._data[field].clear()
    store._save()
    store = type(store)(str(tmp_path))
    result = store.undo_last_review()
    assert result["ok"] and result["card"] == before
    assert store.xp.summary()["total_xp"] == 0
    assert len(store.review_log.entries()) == 2
    assert not store.undo_last_review()["ok"]


def test_undo_recomputes_mastered_count(tmp_path):
    store = LanguageStore(str(tmp_path))
    identifier = store.add_vocabulary("hello", "olá")
    store.review_vocabulary(identifier, 3)
    store._data["stats"]["vocab_mastered"] = 1
    assert store.undo_last_review()["ok"]
    assert store.get_progress()["stats"]["vocab_mastered"] == 0
