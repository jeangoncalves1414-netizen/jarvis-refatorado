from __future__ import annotations

import copy
import json
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from app.storage.tutor.fsrs import apply_review, is_due


DEFAULT_PROGRESS: dict[str, Any] = {
    "schema_version": 1,
    "topic": "Preparação ENEM",
    "current_stage": "00-diagnostico",
    "learner": {"goal": "Aprovação no ENEM", "started": str(date.today())},
    "stats": {
        "sessions": 0,
        "concepts_mastered": 0,
        "flashcards_total": 0,
        "flashcards_due": 0,
        "questions_solved": 0,
        "last_session_date": None,
    },
    "stages": [
        {"id": "00-diagnostico", "title": "Diagnóstico inicial", "status": "in_progress", "mastery": 0.0},
        {"id": "01-linguagens", "title": "Linguagens e Códigos", "status": "not_started", "mastery": 0.0},
        {"id": "02-humanas", "title": "Ciências Humanas", "status": "not_started", "mastery": 0.0},
        {"id": "03-natureza", "title": "Ciências da Natureza", "status": "not_started", "mastery": 0.0},
        {"id": "04-matematica", "title": "Matemática", "status": "not_started", "mastery": 0.0},
        {"id": "05-redacao", "title": "Redação ENEM", "status": "not_started", "mastery": 0.0},
    ],
    "weak_spots": [],
    "flashcards": [],
    "feynman_attempts": [],
    "assessments": [],
    "last_sessions_summary": [],
    "streak_count": 0,
    "last_study_date": None,
    "total_xp": 0,
    "daily_xp": 0,
    "daily_goal": 100,
}


class TutorStore:
    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = Path(storage_dir or "data/tutor")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.progress_path = self.storage_dir / "progress.json"
        self._data: dict[str, Any] = {}
        self._load()

    def _load(self) -> None:
        if self.progress_path.exists():
            try:
                self._data = json.loads(self.progress_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self._data = copy.deepcopy(DEFAULT_PROGRESS)
        else:
            self._data = copy.deepcopy(DEFAULT_PROGRESS)
            self._save()

    def _save(self) -> None:
        self.progress_path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_progress(self) -> dict[str, Any]:
        return dict(self._data)

    def get_summary_for_llm(self) -> str:
        stats = self._data.get("stats", {})
        stage_id = self._data.get("current_stage", "")
        stage_title = next(
            (s["title"] for s in self._data.get("stages", []) if s.get("id") == stage_id),
            stage_id,
        )
        weak = ", ".join(self._data.get("weak_spots", [])[:8]) or "nenhum registrado"
        summaries = self._data.get("last_sessions_summary", [])[-3:]
        lines = [
            f"Etapa atual: {stage_title} ({stage_id})",
            f"Sessões: {stats.get('sessions', 0)} | Questões resolvidas: {stats.get('questions_solved', 0)}",
            f"Flashcards: {stats.get('flashcards_total', 0)} total, {stats.get('flashcards_due', 0)} para revisar",
            f"Pontos fracos: {weak}",
        ]
        if summaries:
            lines.append("Últimas sessões: " + " | ".join(summaries))
        return "\n".join(lines)

    def save_progress(
        self,
        stage_id: str | None = None,
        concept: str | None = None,
        mastered: bool = False,
        session_summary: str | None = None,
        question_solved: bool = False,
    ) -> None:
        if stage_id:
            self._data["current_stage"] = stage_id
            for stage in self._data.setdefault("stages", []):
                if stage.get("id") == stage_id:
                    stage["status"] = "in_progress"
                    if mastered and concept:
                        stage["mastery"] = min(1.0, float(stage.get("mastery", 0)) + 0.05)

        stats = self._data.setdefault("stats", {})
        stats["sessions"] = int(stats.get("sessions", 0)) + (1 if session_summary else 0)
        stats["last_session_date"] = str(date.today())
        if question_solved:
            stats["questions_solved"] = int(stats.get("questions_solved", 0)) + 1
        if mastered and concept:
            stats["concepts_mastered"] = int(stats.get("concepts_mastered", 0)) + 1

        if session_summary:
            summaries = self._data.setdefault("last_sessions_summary", [])
            summaries.append(session_summary[:200])
            self._data["last_sessions_summary"] = summaries[-10:]

        self._save()

    def _normalize_card(self, card: dict[str, Any]) -> dict[str, Any]:
        card.setdefault("difficulty", 5.0)
        card.setdefault("stability", 1.0)
        card.setdefault("ease", 2.3)
        card.setdefault("interval", 0)
        card.setdefault("reps", 0)
        card.setdefault("lapses", 0)
        card.setdefault("due", str(date.today()))
        return card

    def _refresh_flashcard_stats(self) -> None:
        cards = self._data.setdefault("flashcards", [])
        stats = self._data.setdefault("stats", {})
        stats["flashcards_total"] = len(cards)
        stats["flashcards_due"] = sum(1 for c in cards if is_due(c))

    def add_flashcard(self, front: str, back: str, topic: str = "", stage: str = "") -> str:
        cards = self._data.setdefault("flashcards", [])
        card_id = f"fc-{len(cards) + 1:04d}"
        cards.append(self._normalize_card({
            "id": card_id,
            "front": front,
            "back": back,
            "topic": topic or self._data.get("current_stage", ""),
            "stage": stage or self._data.get("current_stage", ""),
            "created": str(date.today()),
        }))
        self._refresh_flashcard_stats()
        self._save()
        return card_id

    def get_flashcards(self) -> list[dict[str, Any]]:
        return [self._normalize_card(dict(c)) for c in self._data.get("flashcards", [])]

    def get_due_flashcards(self) -> list[dict[str, Any]]:
        return [c for c in self.get_flashcards() if is_due(c)]

    def review_flashcard(self, card_id: str, grade: int) -> dict[str, Any] | None:
        cards = self._data.setdefault("flashcards", [])
        for card in cards:
            if card.get("id") != card_id:
                continue
            self._normalize_card(card)
            result = apply_review(card, grade)
            card.update({
                "interval": result.interval,
                "ease": result.ease,
                "reps": result.reps,
                "lapses": result.lapses,
                "due": result.due,
                "difficulty": getattr(result, "difficulty", 5.0),
                "stability": getattr(result, "stability", 1.0),
                "last_review": str(date.today()),
            })
            self._refresh_flashcard_stats()
            self._save()
            return dict(card)
        return None

    def add_feynman_attempt(
        self,
        topic: str,
        explanation: str,
        grade: int | None = None,
        feedback: str = "",
    ) -> str:
        attempts = self._data.setdefault("feynman_attempts", [])
        attempt_id = f"fy-{len(attempts) + 1:04d}"
        attempts.append({
            "id": attempt_id,
            "topic": topic,
            "explanation": explanation[:2000],
            "grade": grade,
            "feedback": feedback[:1000],
            "date": str(date.today()),
        })
        self._data["feynman_attempts"] = attempts[-50:]
        stats = self._data.setdefault("stats", {})
        stats["feynman_attempts"] = int(stats.get("feynman_attempts", 0)) + 1
        if grade is not None and grade < 3 and topic:
            self.add_weak_spot(topic)
        self._save()
        return attempt_id

    def get_feynman_attempts(self) -> list[dict[str, Any]]:
        return list(self._data.get("feynman_attempts", []))

    def add_assessment(
        self,
        stage_id: str,
        correct: int,
        total: int,
        weak_topics: list[str] | None = None,
    ) -> str:
        assessments = self._data.setdefault("assessments", [])
        assessment_id = f"as-{len(assessments) + 1:04d}"
        score = round(correct / total, 2) if total else 0.0
        assessments.append({
            "id": assessment_id,
            "stage_id": stage_id,
            "correct": correct,
            "total": total,
            "score": score,
            "weak_topics": weak_topics or [],
            "date": str(date.today()),
        })
        self._data["assessments"] = assessments[-30:]
        stats = self._data.setdefault("stats", {})
        stats["quizzes_taken"] = int(stats.get("quizzes_taken", 0)) + 1
        for topic in weak_topics or []:
            self.add_weak_spot(topic)
        self._save()
        return assessment_id

    def get_assessments(self) -> list[dict[str, Any]]:
        return list(self._data.get("assessments", []))

    def get_dashboard(self) -> dict[str, Any]:
        progress = self.get_progress()
        return {
            "progress": progress,
            "due_flashcards": len(self.get_due_flashcards()),
            "weak_spots": progress.get("weak_spots", []),
            "recent_feynman": self.get_feynman_attempts()[-5:],
            "recent_assessments": self.get_assessments()[-5:],
        }

    def add_weak_spot(self, topic: str) -> None:
        weak = self._data.setdefault("weak_spots", [])
        if topic and topic not in weak:
            weak.append(topic)
            self._data["weak_spots"] = weak[-30:]
            self._save()

    # ── Streak & XP ──────────────────────────────────────────────

    def _update_streak(self) -> None:
        today_str = str(date.today())
        last = self._data.get("last_study_date")
        if last == today_str:
            return
        if last:
            try:
                last_date = date.fromisoformat(last)
                diff = (date.today() - last_date).days
                if diff == 1:
                    self._data["streak_count"] = int(self._data.get("streak_count", 0)) + 1
                elif diff > 1:
                    self._data["streak_count"] = 1
            except (ValueError, TypeError):
                self._data["streak_count"] = 1
        else:
            self._data["streak_count"] = 1
        self._data["last_study_date"] = today_str
        self._data["daily_xp"] = 0

    def add_xp(self, amount: int) -> int:
        self._update_streak()
        self._data["total_xp"] = int(self._data.get("total_xp", 0)) + amount
        self._data["daily_xp"] = int(self._data.get("daily_xp", 0)) + amount
        self._save()
        return self._data["total_xp"]

    def get_streak_info(self) -> dict[str, Any]:
        return {
            "streak_count": self._data.get("streak_count", 0),
            "last_study_date": self._data.get("last_study_date"),
            "total_xp": self._data.get("total_xp", 0),
            "daily_xp": self._data.get("daily_xp", 0),
            "daily_goal": self._data.get("daily_goal", 100),
        }
