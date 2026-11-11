"""Tests for LanguageStore — vocabulary, pronunciation, CEFR, streaks."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.storage.language_store import LanguageStore


# ── Fixtures ─────────────────────────────────────────────────────

@pytest.fixture()
def store(tmp_path: Path) -> LanguageStore:
    """LanguageStore backed by a temp directory."""
    return LanguageStore(storage_dir=str(tmp_path))


# ── Vocabulary CRUD ─────────────────────────────────────────────

class TestVocabulary:
    def test_add_vocabulary_returns_id(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("hello", "olá", example="Hello world")
        assert card_id.startswith("voc-")

    def test_get_vocabulary_after_add(self, store: LanguageStore) -> None:
        store.add_vocabulary("hello", "olá")
        vocab = store.get_vocabulary()
        assert len(vocab) == 1
        assert vocab[0]["word"] == "hello"
        assert vocab[0]["translation"] == "olá"

    def test_add_duplicate_is_noop(self, store: LanguageStore) -> None:
        id1 = store.add_vocabulary("hello", "olá")
        id2 = store.add_vocabulary("Hello", "oi")  # same word, different case
        assert id1 == id2
        assert len(store.get_vocabulary()) == 1

    def test_get_vocabulary_contains_fsrs_fields(self, store: LanguageStore) -> None:
        store.add_vocabulary("cat", "gato")
        card = store.get_vocabulary()[0]
        for field in ("difficulty", "stability", "reps", "lapses", "due"):
            assert field in card, f"missing FSRS field: {field}"


# ── Due vocabulary ───────────────────────────────────────────────

class TestDueVocabulary:
    def test_new_card_is_due_immediately(self, store: LanguageStore) -> None:
        store.add_vocabulary("sun", "sol")
        due = store.get_due_vocabulary()
        assert len(due) == 1

    def test_reviewed_card_not_immediately_due(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("moon", "lua")
        result = store.review_vocabulary(card_id, 3)  # grade EASY → graduates to review
        assert result is not None and result["state"] == "review"
        due = store.get_due_vocabulary()
        assert len(due) == 0

    def test_good_on_new_card_stays_in_learning(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("star", "estrela")
        result = store.review_vocabulary(card_id, 2)  # grade GOOD → next learning step
        assert result is not None and result["state"] == "learning"
        assert store.get_due_vocabulary() == []

    def test_legacy_card_reviews_without_error(self, store: LanguageStore) -> None:
        store._data["vocabulary"].append({
            "id": "voc-legacy01", "word": "tree", "translation": "árvore",
            "difficulty": 5.0, "stability": 4.0, "reps": 2, "lapses": 0,
            "due": str(date.today()), "last_review": "2026-01-01",
        })
        assert [c["id"] for c in store.get_due_vocabulary()] == ["voc-legacy01"]
        result = store.review_vocabulary("voc-legacy01", 2)
        assert result is not None and result["state"] == "review"
        assert result["reps"] == 3

    def test_invalid_grade_raises(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("rain", "chuva")
        with pytest.raises(ValueError):
            store.review_vocabulary(card_id, 4)


# ── Review vocabulary ────────────────────────────────────────────

class TestReviewVocabulary:
    def test_review_updates_fsrs_fields(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("dog", "cachorro")
        result = store.review_vocabulary(card_id, 2)
        assert result is not None
        assert result["reps"] == 1
        assert "difficulty" in result
        assert "stability" in result
        assert "due" in result

    def test_review_nonexistent_returns_none(self, store: LanguageStore) -> None:
        assert store.review_vocabulary("voc-doesnotexist", 2) is None

    def test_review_adds_xp(self, store: LanguageStore) -> None:
        card_id = store.add_vocabulary("fish", "peixe")
        store.review_vocabulary(card_id, 2)
        dashboard = store.get_dashboard()
        assert dashboard["total_xp"] > 0


# ── Pronunciation ────────────────────────────────────────────────

class TestPronunciation:
    def test_save_pronunciation_attempt(self, store: LanguageStore) -> None:
        attempt_id = store.save_pronunciation_attempt(
            target="hello world",
            transcript="hello word",
            score=85.0,
            confidence=0.92,
            wrong_words=["world"],
        )
        assert attempt_id.startswith("pron-")

    def test_get_pronunciation_history(self, store: LanguageStore) -> None:
        store.save_pronunciation_attempt("hi", "hi", score=100.0)
        history = store.get_pronunciation_history()
        assert len(history) == 1
        assert history[0]["target"] == "hi"
        assert history[0]["score"] == 100.0

    def test_pronunciation_increments_sessions(self, store: LanguageStore) -> None:
        store.save_pronunciation_attempt("test", "test", score=90.0)
        store.save_pronunciation_attempt("test2", "test2", score=80.0)
        dashboard = store.get_dashboard()
        assert dashboard["stats"]["pronunciation_sessions"] == 2


# ── CEFR level ───────────────────────────────────────────────────

class TestCEFR:
    def test_set_cefr_level(self, store: LanguageStore) -> None:
        store.set_cefr_level("B2")
        assert store.get_progress()["cefr_level"] == "B2"
        assert store.get_progress()["placement_done"] is True

    def test_invalid_cefr_level_ignored(self, store: LanguageStore) -> None:
        store.set_cefr_level("X9")
        assert store.get_progress()["cefr_level"] == "A1"  # unchanged


# ── Streak & XP ──────────────────────────────────────────────────

class TestStreakAndXP:
    def test_add_xp_returns_total(self, store: LanguageStore) -> None:
        total = store.add_xp(25)
        assert total == 25
        total = store.add_xp(10)
        assert total == 35

    def test_add_xp_sets_streak_to_at_least_1(self, store: LanguageStore) -> None:
        store.add_xp(10)
        dashboard = store.get_dashboard()
        assert dashboard["streak"] >= 1

    def test_dashboard_reflects_xp(self, store: LanguageStore) -> None:
        store.add_xp(50)
        d = store.get_dashboard()
        assert d["total_xp"] == 50
        assert d["daily_xp"] == 50


# ── Dashboard structure ──────────────────────────────────────────

class TestDashboard:
    def test_dashboard_has_expected_keys(self, store: LanguageStore) -> None:
        d = store.get_dashboard()
        expected_keys = {
            "cefr_level",
            "target_language",
            "placement_done",
            "stats",
            "due_vocabulary",
            "weak_phonemes",
            "recent_pronunciation",
            "streak",
            "daily_xp",
            "daily_goal",
            "total_xp",
        }
        assert expected_keys.issubset(d.keys())

    def test_dashboard_defaults(self, store: LanguageStore) -> None:
        d = store.get_dashboard()
        assert d["cefr_level"] == "A1"
        assert d["target_language"] == "en"
        assert d["placement_done"] is False
        assert d["due_vocabulary"] == 0
        assert d["daily_goal"] == 50
