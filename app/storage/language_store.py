"""Language learning storage — vocabulary, pronunciation, CEFR progression."""
from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from app.storage.tutor.review_log import ReviewLog, restore, snapshot
from app.storage.tutor.fsrs import (
    apply_review,
    is_due,
    new_card_fields,
    normalize_card,
    review_fields,
    sort_due,
    validate_grade,
)

CEFR_LEVELS = ["A1", "A2", "B1", "B2", "C1", "C2"]

DEFAULT_LANGUAGE_PROGRESS: dict[str, Any] = {
    "schema_version": 1,
    "target_language": "en",
    "native_language": "pt-BR",
    "cefr_level": "A1",
    "placement_done": False,
    "stats": {
        "total_vocab": 0,
        "vocab_mastered": 0,
        "pronunciation_sessions": 0,
        "conversation_sessions": 0,
        "shadowing_sessions": 0,
        "streak_count": 0,
        "last_study_date": None,
        "total_xp": 0,
        "daily_xp": 0,
        "daily_goal": 50,
    },
    "vocabulary": [],
    "pronunciation_history": [],
    "conversation_history": [],
    "weak_phonemes": [],
    "topics_completed": [],
}

# XP rewards
XP_VOCAB_REVIEW = 10
XP_PRONUNCIATION = 15
XP_CONVERSATION = 25
XP_SHADOWING = 20
XP_QUIZ_CORRECT = 5
XP_STREAK_BONUS = 10


class LanguageStore:
    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "data/language")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.progress_path = self.storage_dir / "progress.json"
        self.review_log = ReviewLog(self.storage_dir / "review_log.jsonl")
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.progress_path.exists():
            try:
                self._data = json.loads(self.progress_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = copy.deepcopy(DEFAULT_LANGUAGE_PROGRESS)
        else:
            self._data = copy.deepcopy(DEFAULT_LANGUAGE_PROGRESS)
            self._save()

    def _save(self) -> None:
        self.progress_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── Progress ──────────────────────────────────────────────────

    def get_progress(self) -> dict[str, Any]:
        return dict(self._data)

    def get_summary_for_llm(self) -> str:
        stats = self._data.get("stats", {})
        level = self._data.get("cefr_level", "A1")
        lang = self._data.get("target_language", "en")
        weak = ", ".join(self._data.get("weak_phonemes", [])[:5]) or "nenhum"
        lines = [
            f"Idioma alvo: {lang} | Nível CEFR: {level}",
            f"Vocabulário: {stats.get('total_vocab', 0)} total, {stats.get('vocab_mastered', 0)} dominado",
            f"Pronúncia: {stats.get('pronunciation_sessions', 0)} sessões",
            f"Conversação: {stats.get('conversation_sessions', 0)} sessões",
            f"XP: {stats.get('total_xp', 0)} total | Streak: {stats.get('streak_count', 0)} dias",
            f"Fonemas fracos: {weak}",
        ]
        return "\n".join(lines)

    def set_cefr_level(self, level: str) -> None:
        if level in CEFR_LEVELS:
            self._data["cefr_level"] = level
            self._data["placement_done"] = True
            self._save()

    def set_target_language(self, lang: str) -> None:
        self._data["target_language"] = lang
        self._save()

    # ── Streak & XP ───────────────────────────────────────────────

    def _update_streak(self) -> None:
        stats = self._data.setdefault("stats", {})
        today_str = str(date.today())
        last = stats.get("last_study_date")

        if last == today_str:
            return  # already counted today

        if last:
            try:
                last_date = date.fromisoformat(last)
                diff = (date.today() - last_date).days
                if diff == 1:
                    stats["streak_count"] = int(stats.get("streak_count", 0)) + 1
                elif diff > 1:
                    stats["streak_count"] = 1  # streak broken
            except (ValueError, TypeError):
                stats["streak_count"] = 1
        else:
            stats["streak_count"] = 1

        stats["last_study_date"] = today_str
        stats["daily_xp"] = 0  # reset daily XP

    def add_xp(self, amount: int) -> int:
        self._update_streak()
        stats = self._data.setdefault("stats", {})
        stats["total_xp"] = int(stats.get("total_xp", 0)) + amount
        stats["daily_xp"] = int(stats.get("daily_xp", 0)) + amount
        self._save()
        return stats["total_xp"]

    def set_daily_goal(self, xp: int) -> None:
        self._data.setdefault("stats", {})["daily_goal"] = max(10, min(500, xp))
        self._save()

    # ── Vocabulary ────────────────────────────────────────────────

    def _normalize_vocab(self, card: dict[str, Any]) -> dict[str, Any]:
        normalize_card(card)
        card.setdefault("cefr", self._data.get("cefr_level", "A1"))
        card.setdefault("category", "general")
        return card

    def add_vocabulary(
        self,
        word: str,
        translation: str,
        example: str = "",
        phonetic: str = "",
        category: str = "general",
        cefr: str = "",
    ) -> str:
        vocab = self._data.setdefault("vocabulary", [])
        # Avoid duplicates
        for v in vocab:
            if v.get("word", "").lower() == word.lower():
                return v.get("id", "")
        card_id = f"voc-{uuid.uuid4().hex[:8]}"
        vocab.append(self._normalize_vocab({
            "id": card_id,
            "word": word,
            "translation": translation,
            "example": example,
            "phonetic": phonetic,
            "category": category or "general",
            "cefr": cefr or self._data.get("cefr_level", "A1"),
            "created": str(date.today()),
            **new_card_fields(),
        }))
        stats = self._data.setdefault("stats", {})
        stats["total_vocab"] = len(vocab)
        self._save()
        return card_id

    def get_vocabulary(self) -> list[dict[str, Any]]:
        return [self._normalize_vocab(dict(v)) for v in self._data.get("vocabulary", [])]

    def get_due_vocabulary(self) -> list[dict[str, Any]]:
        return sort_due([v for v in self.get_vocabulary() if is_due(v)])

    def review_vocabulary(self, card_id: str, grade: int) -> dict[str, Any] | None:
        validate_grade(grade)
        vocab = self._data.setdefault("vocabulary", [])
        for card in vocab:
            if card.get("id") != card_id:
                continue
            before = snapshot(card)
            self._normalize_vocab(card)
            state_before = card["state"]
            result = apply_review(card, grade)
            card.update(review_fields(result))
            after = snapshot(card)
            # Track mastered cards
            stats = self._data.setdefault("stats", {})
            if result.reps >= 3 and result.stability >= 10:
                stats["vocab_mastered"] = sum(
                    1 for v in vocab
                    if (v.get("reps") or 0) >= 3 and (v.get("stability") or 0) >= 10
                )
            self.add_xp(XP_VOCAB_REVIEW)
            self._save()
            entry = self.review_log.append({
                "type": "review",
                "deck": "language",
                "card_id": card_id,
                "grade": grade,
                "rating": grade + 1,
                "reviewed_at": result.last_review,
                "local_date": str(date.today()),
                "state_before": state_before,
                "state_after": result.state,
                "retrievability_before": result.retrievability,
                "interval_days": result.interval,
                "xp": XP_VOCAB_REVIEW,
                "before": before,
                "after": after,
            })
            return {**card, "review_id": entry["id"]}
        return None

    def undo_last_review(self) -> dict[str, Any]:
        entry = self.review_log.last_active_review()
        if not entry:
            return {"ok": False, "error": "nothing_to_undo"}
        card = next((v for v in self._data.get("vocabulary", []) if v.get("id") == entry.get("card_id")), None)
        if card is None:
            return {"ok": False, "error": "card_not_found"}
        if snapshot(card) != entry.get("after"):
            return {"ok": False, "error": "stale"}
        restore(card, entry.get("before") or {})
        xp = int(entry.get("xp") or 0)
        stats = self._data.setdefault("stats", {})
        stats["total_xp"] = max(0, int(stats.get("total_xp", 0)) - xp)
        stats["daily_xp"] = max(0, int(stats.get("daily_xp", 0)) - xp)
        self._save()
        self.review_log.append({
            "type": "undo",
            "target": entry["id"],
            "undone_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"ok": True, "card": dict(card), "undone_review_id": entry["id"]}

    # ── Pronunciation ─────────────────────────────────────────────

    def save_pronunciation_attempt(
        self,
        target: str,
        transcript: str,
        score: float,
        confidence: float = 0.0,
        wrong_words: list[str] | None = None,
    ) -> str:
        attempts = self._data.setdefault("pronunciation_history", [])
        attempt_id = f"pron-{uuid.uuid4().hex[:8]}"
        attempts.append({
            "id": attempt_id,
            "target": target,
            "transcript": transcript,
            "score": round(score, 1),
            "confidence": round(confidence, 3),
            "wrong_words": wrong_words or [],
            "date": str(date.today()),
        })
        self._data["pronunciation_history"] = attempts[-100:]
        stats = self._data.setdefault("stats", {})
        stats["pronunciation_sessions"] = int(stats.get("pronunciation_sessions", 0)) + 1
        self.add_xp(XP_PRONUNCIATION)
        self._save()
        return attempt_id

    def get_pronunciation_history(self) -> list[dict[str, Any]]:
        return list(self._data.get("pronunciation_history", []))

    def add_weak_phoneme(self, phoneme: str) -> None:
        weak = self._data.setdefault("weak_phonemes", [])
        if phoneme and phoneme not in weak:
            weak.append(phoneme)
            self._data["weak_phonemes"] = weak[-20:]
            self._save()

    # ── Conversation ──────────────────────────────────────────────

    def log_conversation_session(
        self,
        topic: str,
        corrections: int = 0,
        new_vocab: list[str] | None = None,
        duration_minutes: int = 0,
    ) -> str:
        history = self._data.setdefault("conversation_history", [])
        session_id = f"conv-{uuid.uuid4().hex[:8]}"
        history.append({
            "id": session_id,
            "topic": topic,
            "corrections": corrections,
            "new_vocab": new_vocab or [],
            "duration": duration_minutes,
            "date": str(date.today()),
        })
        self._data["conversation_history"] = history[-50:]
        stats = self._data.setdefault("stats", {})
        stats["conversation_sessions"] = int(stats.get("conversation_sessions", 0)) + 1
        self.add_xp(XP_CONVERSATION)
        self._save()
        return session_id

    # ── Shadowing ─────────────────────────────────────────────────

    def log_shadowing_session(self, text: str, score: float = 0.0, speed: float = 1.0) -> None:
        stats = self._data.setdefault("stats", {})
        stats["shadowing_sessions"] = int(stats.get("shadowing_sessions", 0)) + 1
        self.add_xp(XP_SHADOWING)
        self._save()

    # ── Dashboard ─────────────────────────────────────────────────

    def get_dashboard(self) -> dict[str, Any]:
        progress = self.get_progress()
        stats = progress.get("stats", {})
        return {
            "cefr_level": progress.get("cefr_level", "A1"),
            "target_language": progress.get("target_language", "en"),
            "placement_done": progress.get("placement_done", False),
            "stats": stats,
            "due_vocabulary": len(self.get_due_vocabulary()),
            "weak_phonemes": progress.get("weak_phonemes", []),
            "recent_pronunciation": self.get_pronunciation_history()[-5:],
            "streak": stats.get("streak_count", 0),
            "daily_xp": stats.get("daily_xp", 0),
            "daily_goal": stats.get("daily_goal", 50),
            "total_xp": stats.get("total_xp", 0),
        }

