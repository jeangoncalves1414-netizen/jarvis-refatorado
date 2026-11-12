"""Lápides (tombstones) da sincronização: registro local do que foi apagado de propósito.

Sem elas, a mesclagem por união traria de volta um item apagado em um
dispositivo assim que outro dispositivo (ou a nuvem) ainda o tivesse.

Regras:
- Cada lápide guarda ``tipo -> chave -> instante da exclusão`` (segundos desde 1970).
- Um item só é removido pela lápide se o carimbo dele (edição, criação ou ``mtime``)
  for menor ou igual ao instante da exclusão. Se foi recriado ou editado depois,
  o item vence e continua vivo.
- Lápides de dispositivos diferentes se unem; para a mesma chave vale o instante
  mais recente. Lápides vindas de fora são validadas e nunca ficam no futuro.
- Lápides com mais de ``RETENTION_SECONDS`` (90 dias) são descartadas. Um
  dispositivo que ficar mais tempo que isso sem sincronizar pode trazer de
  volta um item apagado (limite aceito para o arquivo não crescer sem fim).
- O arquivo local é ``data/sync_tombstones.json``. Registrar uma lápide nunca
  quebra a exclusão: falhas viram aviso no log, sem valores.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import math
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

TOMBSTONES_FILE = Path("data/sync_tombstones.json")

# tipo -> o que a chave identifica
KINDS = frozenset(
    {
        "tasks",  # tarefas de data/tasks.json (id)
        "memory.facts", "memory.preferences", "memory.user_preferences", "memory_facts",
        "notes",  # notas do cofre (caminho relativo .md)
        "lifestyle.habits",  # hábitos (JSON da identidade da linha)
        "lifestyle.habit_logs",
        "lifestyle.tasks",
        "lifestyle.finance_transactions",
    }
)
MAX_KEY_LENGTH = 300
MAX_PER_KIND = 5000
MAX_SEEN_NOTES = 5000
RETENTION_SECONDS = 90 * 24 * 60 * 60

_lock = threading.RLock()
_logger = logging.getLogger(__name__)

Tombstones = dict[str, dict[str, float]]


def clean(raw: Any, now: float | None = None) -> Tombstones:
    """Valida lápides de origem não confiável: tipo conhecido, chave curta, instante finito e não futuro.

    Também descarta as mais antigas que ``RETENTION_SECONDS``.
    """
    now = time.time() if now is None else now
    oldest = now - RETENTION_SECONDS
    result: Tombstones = {}
    if not isinstance(raw, dict):
        return result
    for kind, entries in raw.items():
        if kind not in KINDS or not isinstance(entries, dict):
            continue
        valid: dict[str, float] = {}
        for key, at in entries.items():
            if not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
                continue
            if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at < oldest:
                continue
            valid[key] = float(min(at, now))
        if len(valid) > MAX_PER_KIND:
            newest = sorted(valid.items(), key=lambda item: item[1], reverse=True)[:MAX_PER_KIND]
            valid = dict(newest)
        if valid:
            result[kind] = valid
    return result


def merge(first: Any, second: Any, now: float | None = None) -> Tombstones:
    """União de lápides; na mesma chave vale a exclusão mais recente."""
    merged = clean(first, now)
    for kind, entries in clean(second, now).items():
        target = merged.setdefault(kind, {})
        for key, at in entries.items():
            target[key] = max(at, target.get(key, 0.0))
    return clean(merged, now)


def row_key(*parts: Any) -> str:
    """Chave de uma linha do SQLite: lista JSON dos valores de identidade (mesma de backend_sync)."""
    return json.dumps(list(parts), ensure_ascii=False)


def memory_key(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def covers(tombstones: Tombstones, kind: str, key: str, stamp: float) -> bool:
    """True se a lápide apaga um item cujo último carimbo é ``stamp``."""
    at = tombstones.get(kind, {}).get(key)
    return at is not None and stamp <= at


# ---------------------------------------------------------------------------
# Arquivo local
# ---------------------------------------------------------------------------
def _read() -> dict[str, Any]:
    try:
        data = json.loads(Path(TOMBSTONES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(data: dict[str, Any]) -> None:
    path = Path(TOMBSTONES_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load() -> Tombstones:
    with _lock:
        return clean(_read().get("deleted"))


def store(tombstones: Any) -> None:
    """Une as lápides informadas às locais e grava (nunca esquece uma exclusão)."""
    with _lock:
        data = _read()
        data["version"] = 1
        data["deleted"] = merge(data.get("deleted"), tombstones)
        _write(data)


def record(kind: str, key: str, at: float | None = None) -> None:
    """Registra uma exclusão feita aqui. Nunca levanta exceção."""
    if kind not in KINDS or not isinstance(key, str) or not key or len(key) > MAX_KEY_LENGTH:
        return
    try:
        store({kind: {key: time.time() if at is None else at}})
    except Exception as exc:  # noqa: BLE001 - a exclusão do usuário não pode falhar por causa da lápide
        _logger.warning("Não foi possível registrar a lápide de sincronização (%s).", type(exc).__name__)


# ---------------------------------------------------------------------------
# Notas já vistas (para perceber exclusões feitas direto na pasta do cofre)
# ---------------------------------------------------------------------------
def load_seen_notes() -> tuple[set[str], float]:
    """Notas presentes na última coleta e o instante dessa coleta (0 se nunca houve)."""
    with _lock:
        data = _read()
    raw, at = data.get("seen_notes"), data.get("seen_notes_at")
    if not isinstance(raw, list):
        return set(), 0.0
    if isinstance(at, bool) or not isinstance(at, (int, float)) or not math.isfinite(at) or at < 0:
        at = 0.0
    return {item for item in raw if isinstance(item, str) and 0 < len(item) <= MAX_KEY_LENGTH}, float(at)


def save_seen_notes(paths: set[str], at: float | None = None) -> None:
    with _lock:
        data = _read()
        data["version"] = 1
        data["seen_notes"] = sorted(paths)[:MAX_SEEN_NOTES]
        data["seen_notes_at"] = time.time() if at is None else at
        with contextlib.suppress(OSError):
            _write(data)
