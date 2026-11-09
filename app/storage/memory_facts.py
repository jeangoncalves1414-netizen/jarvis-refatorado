"""Memórias com fonte (fase contexto 2, J5): ``data/memory_facts.json``, versão 1.

Cada fato guarda texto, slot opcional (``music``, ``city``, ``app.<categoria>``), valor,
período e a fonte (data, conversa, run, origem chat/voz/painel e tipo gatilho/extração/manual).
Exclusão é suave (``deleted_at``, lápide local) e ``updated_at`` acompanha cada mudança,
para o arquivo poder entrar na sincronização depois. O caminho é lido na hora da chamada
(``runtime_settings.DATA_DIR``) para os testes isolarem sem tocar em ``data/``.
"""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from app.services import memory_slots
from app.storage import runtime_settings

VERSION = 1
MAX_TEXT = 300
MAX_LIVE = 500
ORIGINS = ("chat", "voz", "painel")
KINDS = ("gatilho", "extracao", "manual")

_lock = threading.RLock()
_WORD = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = frozenset({
    "que", "para", "pra", "com", "uma", "uns", "umas", "por", "mais", "como", "isso", "essa", "esse", "este", "esta",
    "meu", "minha", "seu", "sua", "voce", "nao", "sim", "dos", "das", "nos", "nas", "pelo", "pela", "quando",
    "prefere", "prefiro", "usuario", "usuaria", "gosta", "gosto", "sempre", "lembra", "lembre", "jarvis",
})
# Assunto do pedido -> slot que ganha bônus na relevância.
_SUBJECTS = (
    (frozenset({"musica", "musicas", "tocar", "toca", "toque", "playlist", "ouvir", "escutar", "spotify", "som"}), ("music",)),
    (frozenset({"clima", "tempo", "chover", "chuva", "temperatura", "previsao", "perto", "lugar", "lugares",
                "restaurante", "farmacia", "mercado", "onde", "proximo", "proxima"}), ("city",)),
    (frozenset({"abrir", "abre", "abra", "app", "aplicativo", "programa", "navegador", "editor", "player"}),
     ("app.navegador", "app.editor", "app.player")),
)


def facts_path() -> Path:
    return Path(runtime_settings.DATA_DIR) / "memory_facts.json"


def _read() -> list[dict[str, Any]]:
    try:
        data = json.loads(facts_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    facts = data.get("facts") if isinstance(data, dict) else None
    return [fact for fact in facts if isinstance(fact, dict) and isinstance(fact.get("id"), str)] if isinstance(facts, list) else []


def _write(facts: list[dict[str, Any]]) -> None:
    path = facts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump({"version": VERSION, "facts": facts}, handle, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _norm(text: str) -> str:
    return " ".join(memory_slots.normalize_aligned(text).split())


def _clean_text(text: Any) -> str:
    value = " ".join(str(text or "").split())
    if not value:
        raise ValueError("Escreva o texto da memória.")
    if len(value) > MAX_TEXT:
        raise ValueError(f"A memória pode ter no máximo {MAX_TEXT} caracteres.")
    return value


def _clean_source(source: dict[str, Any] | None, now: float) -> dict[str, Any]:
    source = source if isinstance(source, dict) else {}
    origin = source.get("origin") if source.get("origin") in ORIGINS else "chat"
    kind = source.get("kind") if source.get("kind") in KINDS else "manual"
    created = source.get("created_at")
    return {
        "created_at": float(created) if isinstance(created, (int, float)) and not isinstance(created, bool) else now,
        "session_id": str(source.get("session_id") or "")[:120],
        "run_id": str(source.get("run_id") or "")[:120],
        "origin": origin,
        "kind": kind,
    }


def _apply_slot(fact: dict[str, Any], slot: str | None, value: str | None, when: str | None) -> None:
    if slot is None:
        parsed = memory_slots.parse(fact["text"])
        slot, value, when = parsed if parsed else (None, None, None)
    fact["slot"] = slot if slot in memory_slots.SLOTS else None
    fact["value"] = str(value)[: memory_slots.MAX_VALUE] if fact["slot"] and value else None
    fact["when"] = when if fact["slot"] == "music" and when in ("manha", "tarde", "noite") else None


def _live(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [fact for fact in facts if not fact.get("deleted_at")]


def list_facts(include_deleted: bool = False) -> list[dict[str, Any]]:
    """Fatos mais recentes primeiro."""
    with _lock:
        facts = _read()
    chosen = facts if include_deleted else _live(facts)
    return sorted(chosen, key=lambda fact: float(fact.get("updated_at") or 0), reverse=True)


def get(fact_id: str) -> dict[str, Any] | None:
    return next((fact for fact in _read() if fact.get("id") == fact_id), None)


def save(text: str, *, source: dict[str, Any] | None = None, slot: str | None = None,
         value: str | None = None, when: str | None = None) -> dict[str, Any]:
    """Grava um fato; duplicata viva (mesmo texto sem acento) só atualiza ``updated_at``."""
    clean = _clean_text(text)
    now = time.time()
    with _lock:
        facts = _read()
        key = _norm(clean)
        for fact in _live(facts):
            if _norm(fact.get("text", "")) == key:
                fact["updated_at"] = now
                _write(facts)
                return dict(fact)
        fact: dict[str, Any] = {"id": f"mem_{uuid.uuid4().hex[:12]}", "text": clean}
        _apply_slot(fact, slot, value, when)
        fact.update(source=_clean_source(source, now), updated_at=now, deleted_at=None)
        facts.append(fact)
        live = sorted(_live(facts), key=lambda item: float(item.get("updated_at") or 0))
        for old in live[: max(0, len(live) - MAX_LIVE)]:
            old["deleted_at"] = old["updated_at"] = now
        _write(facts)
        return dict(fact)


def update(fact_id: str, text: str) -> dict[str, Any]:
    """Troca o texto, reaplica o parser e atualiza ``updated_at``."""
    clean = _clean_text(text)
    with _lock:
        facts = _read()
        fact = next((item for item in _live(facts) if item.get("id") == fact_id), None)
        if fact is None:
            raise ValueError("Memória não encontrada.")
        fact["text"] = clean
        _apply_slot(fact, None, None, None)
        fact["updated_at"] = time.time()
        _write(facts)
        return dict(fact)


def delete(fact_id: str) -> dict[str, Any]:
    """Exclusão suave: marca ``deleted_at`` (lápide local)."""
    with _lock:
        facts = _read()
        fact = next((item for item in _live(facts) if item.get("id") == fact_id), None)
        if fact is None:
            raise ValueError("Memória não encontrada.")
        fact["deleted_at"] = fact["updated_at"] = time.time()
        _write(facts)
        return dict(fact)


def _words(text: str) -> set[str]:
    return {word for word in _WORD.findall(_norm(text)) if word not in _STOPWORDS}


def relevant(text: str, limit: int = 3, facts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Fatos mais ligados ao pedido: palavras em comum (≥ 3 letras) + bônus do assunto do slot."""
    words = _words(text)
    if not words:
        return []
    bonus_slots = {slot for subject, slots in _SUBJECTS if words & subject for slot in slots}
    scored = []
    for fact in list_facts() if facts is None else facts:
        score = len(words & _words(fact.get("text", "")))
        if fact.get("slot") in bonus_slots:
            score += 2
        if score > 0:
            scored.append((score, float(fact.get("updated_at") or 0), fact))
    scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [fact for _score, _at, fact in scored[:limit]]
