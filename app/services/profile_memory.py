"""Memoria local isolada por perfil de identidade.

Esta camada fica separada da memoria semantica global. Ela guarda apenas texto
curto e metadados, sem enviar nada para provedores externos. O perfil precisa
ser identificado antes de entrar no contexto de uma conversa.
"""
from __future__ import annotations

import json
import re
import secrets
import threading
import time
from pathlib import Path
from typing import Any

DATA_DIR = Path("data")
PROFILE_MEMORY_FILE = DATA_DIR / "profile_memories.json"
MAX_PER_PROFILE = 500
MAX_TEXT_LENGTH = 2_000
_lock = threading.RLock()


def _read() -> dict[str, list[dict[str, Any]]]:
    try:
        value = json.loads(PROFILE_MEMORY_FILE.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data: dict[str, list[dict[str, Any]]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = PROFILE_MEMORY_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(PROFILE_MEMORY_FILE)


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[\wÀ-ÿ]{3,}", value.lower()) if token not in {"para", "sobre", "como", "que", "uma", "com"}}


class ProfileMemoryStore:
    """CRUD e recuperação simples de memórias privadas de cada identidade."""

    def count(self, profile_id: str) -> int:
        with _lock:
            return len(_read().get(str(profile_id), []))

    def add(
        self,
        profile_id: str,
        text: str,
        *,
        kind: str = "note",
        importance: float = 0.5,
        source: str = "conversation",
    ) -> dict[str, Any] | None:
        profile_id = str(profile_id or "").strip()
        text = " ".join(str(text or "").split()).strip()[:MAX_TEXT_LENGTH]
        if not profile_id or len(text) < 3:
            return None
        now = time.time()
        record = {
            "id": secrets.token_urlsafe(12),
            "profile_id": profile_id,
            "text": text,
            "kind": kind if kind in {"note", "fact", "preference", "conversation"} else "note",
            "importance": max(0.0, min(1.0, float(importance))),
            "source": str(source or "local")[:40],
            "created_at": now,
            "updated_at": now,
            "access_count": 0,
        }
        with _lock:
            data = _read()
            items = data.setdefault(profile_id, [])
            # Evita registrar a mesma fala várias vezes em reconexões do chat.
            duplicate = next((item for item in items if item.get("text") == text and item.get("kind") == record["kind"]), None)
            if duplicate:
                duplicate["updated_at"] = now
                duplicate["access_count"] = int(duplicate.get("access_count", 0)) + 1
                _write(data)
                return dict(duplicate)
            items.append(record)
            if len(items) > MAX_PER_PROFILE:
                items.sort(key=lambda item: (float(item.get("importance", 0.5)), float(item.get("updated_at", 0))))
                del items[:-MAX_PER_PROFILE]
            _write(data)
        return dict(record)

    def list(self, profile_id: str, *, query: str = "", limit: int = 50) -> list[dict[str, Any]]:
        profile_id = str(profile_id or "").strip()
        query_tokens = _tokens(query)
        limit = max(1, min(int(limit or 50), 200))
        with _lock:
            items = [dict(item) for item in _read().get(profile_id, [])]
        if query_tokens:
            ranked: list[tuple[float, dict[str, Any]]] = []
            for item in items:
                overlap = len(query_tokens & _tokens(str(item.get("text", ""))))
                if overlap:
                    ranked.append((overlap + float(item.get("importance", 0.5)) * 0.25, item))
            items = [item for _, item in sorted(ranked, key=lambda pair: (pair[0], pair[1].get("updated_at", 0)), reverse=True)]
        else:
            items.sort(key=lambda item: item.get("updated_at", item.get("created_at", 0)), reverse=True)
        return items[:limit]

    def context(self, profile_id: str, query: str = "", limit: int = 8) -> list[dict[str, Any]]:
        items = self.list(profile_id, query=query, limit=limit)
        if not items:
            return []
        with _lock:
            data = _read()
            stored = data.get(str(profile_id), [])
            ids = {item.get("id") for item in items}
            for item in stored:
                if item.get("id") in ids:
                    item["access_count"] = int(item.get("access_count", 0)) + 1
            _write(data)
        return items

    def delete(self, profile_id: str, memory_id: str) -> bool:
        with _lock:
            data = _read()
            items = data.get(str(profile_id), [])
            kept = [item for item in items if item.get("id") != memory_id]
            if len(kept) == len(items):
                return False
            data[str(profile_id)] = kept
            _write(data)
            return True

    def clear(self, profile_id: str) -> int:
        with _lock:
            data = _read()
            removed = len(data.get(str(profile_id), []))
            if removed:
                data[str(profile_id)] = []
                _write(data)
            return removed

