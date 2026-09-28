"""Registro técnico privado para investigação de falhas locais.

Este arquivo não é uma memória do usuário e não possui rota de leitura no painel.
Ele guarda apenas metadados seguros (nunca áudio, transcrições, prompts ou chaves).
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DIRECTORY = Path.cwd() / "data" / "diagnostics"
_MAX_VALUE_LENGTH = 500
_RETENTION_DAYS = 14
_MAX_TOTAL_BYTES = 10 * 1024 * 1024


def _safe(value: Any) -> Any:
    if isinstance(value, dict):
        sensitive = ("audio", "text", "transcript", "prompt", "token", "secret", "password", "authorization", "api_key")
        return {
            str(key)[:80]: _safe(item)
            for key, item in value.items()
            if not any(part in str(key).lower() for part in sensitive)
        }
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value[:20]]
    if isinstance(value, str):
        return value.replace("\n", " ")[:_MAX_VALUE_LENGTH]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:_MAX_VALUE_LENGTH]


def _apply_retention(current_path: Path) -> None:
    """Mantém os diagnósticos úteis sem deixar o diretório crescer indefinidamente."""
    cutoff = datetime.now().timestamp() - (_RETENTION_DAYS * 24 * 60 * 60)
    files = sorted(_DIRECTORY.glob("jarvis-*.jsonl"), key=lambda item: item.stat().st_mtime)
    for path in files:
        if path != current_path and path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)
    files = sorted(_DIRECTORY.glob("jarvis-*.jsonl"), key=lambda item: item.stat().st_mtime)
    total_bytes = sum(path.stat().st_size for path in files)
    for path in files:
        if total_bytes <= _MAX_TOTAL_BYTES or path == current_path:
            continue
        total_bytes -= path.stat().st_size
        path.unlink(missing_ok=True)


def record(component: str, event: str, level: str = "INFO", **context: Any) -> None:
    """Acrescenta um evento técnico; falhas de log nunca afetam o app."""
    try:
        now = datetime.now()
        entry = {
            "timestamp": now.isoformat(timespec="milliseconds"),
            "level": level.upper(),
            "component": component[:80],
            "event": event[:160],
            "context": _safe(context),
        }
        with _LOCK:
            _DIRECTORY.mkdir(parents=True, exist_ok=True)
            path = _DIRECTORY / f"jarvis-{now.date().isoformat()}.jsonl"
            _apply_retention(path)
            with path.open("a", encoding="utf-8") as output:
                output.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
