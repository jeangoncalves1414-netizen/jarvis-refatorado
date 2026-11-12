"""Immutable review log and undo of the last review (tutor + language decks)."""
from __future__ import annotations

import copy
import json
from datetime import date

import pytest

from app.storage.language_store import LanguageStore
from app.storage.tutor_store import TutorStore


@pytest.fixture(params=["tutor", "language"])
def deck(request, tmp_path):
    """(store, add_card, review, cards) for each deck, on a temp dir."""
    if request.param == "tutor":
        store = TutorStore(storage_dir=str(tmp_path / "tutor"))
        return (
            store,
            lambda word: store.add_flashcard(word, "resposta"),
            store.review_flashcard,
            lambda: store._data["flashcards"],
        )
    store = LanguageStore(storage_dir=str(tmp_path / "language"))
    return (
        store,
        lambda word: store.add_vocabulary(word, "tradução"),
        store.review_vocabulary,
        lambda: store._data["vocabulary"],
    )


def _log_lines(store) -> list[str]:
    path = store.review_log.path
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def _card(cards, card_id: str) -> dict:
    return next(c for c in cards() if c["id"] == card_id)


def test_review_writes_one_log_line_with_before_after(deck) -> None:
    store, add, review, cards = deck
    card_id = add("alpha")
    result = review(card_id, 2)

    lines = _log_lines(store)
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert entry["type"] == "review"
    assert entry["id"] == result["review_id"]
    assert entry["id"].startswith("rev-")
    assert entry["card_id"] == card_id
    assert entry["grade"] == 2 and entry["rating"] == 3
    assert entry["state_before"] == "new" and entry["state_after"] == "learning"
    assert entry["retrievability_before"] is None
    assert entry["before"]["values"]["state"] == "new"
    assert entry["after"]["values"]["state"] == "learning"
    assert entry["local_date"] == str(date.today())


def test_undo_restores_exact_legacy_card(deck) -> None:
    store, add, review, cards = deck
    card_id = add("beta")
    card = _card(cards, card_id)
    for key in ("state", "step", "stability", "difficulty", "due", "reps", "lapses"):
        card.pop(key, None)
    card.update({"ease": 2.5, "interval": 3, "reps": 2, "lapses": 0, "due": str(date.today()),
                 "cefr": "A1", "category": "general"})
    original = copy.deepcopy(card)

    review(card_id, 2)
    assert "state" in _card(cards, card_id)

    result = store.undo_last_review()
    assert result["ok"] is True
    assert _card(cards, card_id) == original
    assert "state" not in _card(cards, card_id)
    assert result["card"] == original


def test_undo_twice_is_newest_first(deck) -> None:
    store, add, review, cards = deck
    card_id = add("gamma")
    pristine = copy.deepcopy(_card(cards, card_id))
    first = review(card_id, 2)
    after_first = copy.deepcopy(_card(cards, card_id))
    second = review(card_id, 2)

    undo1 = store.undo_last_review()
    assert undo1["undone_review_id"] == second["review_id"]
    assert _card(cards, card_id) == after_first

    undo2 = store.undo_last_review()
    assert undo2["undone_review_id"] == first["review_id"]
    assert _card(cards, card_id) == pristine

    assert store.undo_last_review() == {"ok": False, "error": "nothing_to_undo"}


def test_undo_with_nothing(deck) -> None:
    store, _, _, _ = deck
    assert store.undo_last_review() == {"ok": False, "error": "nothing_to_undo"}


def test_undo_stale_after_card_changed(deck) -> None:
    store, add, review, cards = deck
    card_id = add("delta")
    review(card_id, 3)
    _card(cards, card_id)["reps"] = 99
    assert store.undo_last_review() == {"ok": False, "error": "stale"}
    assert _card(cards, card_id)["reps"] == 99


def test_undo_card_not_found(deck) -> None:
    store, add, review, cards = deck
    card_id = add("epsilon")
    review(card_id, 2)
    cards().clear()
    assert store.undo_last_review() == {"ok": False, "error": "card_not_found"}


def test_log_only_grows(deck) -> None:
    store, add, review, _ = deck
    card_id = add("zeta")
    review(card_id, 2)
    review(card_id, 2)
    before = _log_lines(store)
    assert len(before) == 2

    store.undo_last_review()
    after = _log_lines(store)
    assert len(after) == 3
    assert after[:2] == before
    undo = json.loads(after[2])
    assert undo["type"] == "undo"
    assert undo["id"].startswith("undo-")
    assert undo["target"] == json.loads(before[1])["id"]


def test_log_tolerates_corrupt_lines(deck) -> None:
    store, add, review, _ = deck
    card_id = add("eta")
    review(card_id, 2)
    with store.review_log.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    assert len(store.review_log.entries()) == 1
    assert store.undo_last_review()["ok"] is True


def test_language_xp_reverted_on_undo(tmp_path) -> None:
    store = LanguageStore(storage_dir=str(tmp_path / "language"))
    store.add_xp(5)
    card_id = store.add_vocabulary("theta", "teta")
    total_before = store.get_dashboard()["total_xp"]
    daily_before = store.get_dashboard()["daily_xp"]

    store.review_vocabulary(card_id, 2)
    assert store.get_dashboard()["total_xp"] == total_before + 10

    assert store.undo_last_review()["ok"] is True
    assert store.get_dashboard()["total_xp"] == total_before
    assert store.get_dashboard()["daily_xp"] == daily_before


def test_undo_survives_reload(tmp_path) -> None:
    store = TutorStore(storage_dir=str(tmp_path / "tutor"))
    card_id = store.add_flashcard("Q", "A")
    store.review_flashcard(card_id, 3)

    reloaded = TutorStore(storage_dir=str(tmp_path / "tutor"))
    result = reloaded.undo_last_review()
    assert result["ok"] is True
    assert result["card"]["reps"] == 0
    assert result["card"]["state"] == "new"
