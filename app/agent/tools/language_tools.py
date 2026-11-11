"""Language learning tools for AI agent integration."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult


class LanguageAddVocabularyTool(BaseTool):
    def __init__(self, language_store: Any) -> None:
        self._store = language_store

    @property
    def name(self) -> str:
        return "language_add_vocabulary"

    @property
    def description(self) -> str:
        return "Adds a vocabulary word with translation, example sentence, and phonetic transcription to the language learning deck."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "word": {"type": "string", "description": "The word in the target language."},
                "translation": {"type": "string", "description": "Translation in the native language."},
                "example": {"type": "string", "description": "Example sentence using the word."},
                "phonetic": {"type": "string", "description": "IPA or simplified phonetic transcription."},
                "category": {"type": "string", "description": "Category: general, travel, work, food, etc."},
                "cefr": {"type": "string", "description": "CEFR level: A1, A2, B1, B2, C1, C2."},
            },
            "required": ["word", "translation"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        card_id = self._store.add_vocabulary(
            word=str(args.get("word", "")),
            translation=str(args.get("translation", "")),
            example=str(args.get("example", "")),
            phonetic=str(args.get("phonetic", "")),
            category=str(args.get("category", "general")),
            cefr=str(args.get("cefr", "")),
        )
        return ToolResult(ok=True, message=f"Vocabulary added: {args.get('word', '')}", data={"id": card_id})


class LanguageSavePronunciationTool(BaseTool):
    def __init__(self, language_store: Any) -> None:
        self._store = language_store

    @property
    def name(self) -> str:
        return "language_save_pronunciation"

    @property
    def description(self) -> str:
        return "Records a pronunciation practice attempt with target text, transcript, and accuracy score."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {"type": "string", "description": "The text the student was supposed to say."},
                "transcript": {"type": "string", "description": "What the speech recognition heard."},
                "score": {"type": "number", "description": "Pronunciation score (0-100)."},
                "wrong_words": {"type": "array", "items": {"type": "string"}, "description": "Words that were mispronounced."},
            },
            "required": ["target", "transcript", "score"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        attempt_id = self._store.save_pronunciation_attempt(
            target=str(args.get("target", "")),
            transcript=str(args.get("transcript", "")),
            score=float(args.get("score", 0)),
            wrong_words=args.get("wrong_words", []),
        )
        return ToolResult(ok=True, message=f"Pronunciation recorded: {args.get('score', 0)}%", data={"id": attempt_id})


class LanguageAddWeakPhonemeTool(BaseTool):
    def __init__(self, language_store: Any) -> None:
        self._store = language_store

    @property
    def name(self) -> str:
        return "language_add_weak_phoneme"

    @property
    def description(self) -> str:
        return "Marks a phoneme as a weak point for the student to practice."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phoneme": {"type": "string", "description": "The weak phoneme, e.g. 'th', 'r', 'æ'."},
            },
            "required": ["phoneme"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        self._store.add_weak_phoneme(str(args.get("phoneme", "")))
        return ToolResult(ok=True, message=f"Weak phoneme recorded: {args.get('phoneme', '')}")


class LanguageSetLevelTool(BaseTool):
    def __init__(self, language_store: Any) -> None:
        self._store = language_store

    @property
    def name(self) -> str:
        return "language_set_level"

    @property
    def description(self) -> str:
        return "Sets the student's CEFR level after a placement test or manual selection."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["A1", "A2", "B1", "B2", "C1", "C2"], "description": "CEFR level."},
            },
            "required": ["level"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        level = str(args.get("level", "A1")).upper()
        self._store.set_cefr_level(level)
        return ToolResult(ok=True, message=f"CEFR level set to {level}")

