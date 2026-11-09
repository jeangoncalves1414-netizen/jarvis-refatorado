"""Rotas do contexto situacional e das memórias com fonte (fases contexto 1 e 2).

GET/POST /api/settings/context.
GET/POST /api/memories/facts (salvar, editar e remover passam pelo Kernel, origem janela).
"""
from __future__ import annotations

import json
from typing import Any

from app.storage.contexto_settings import get_context_settings, set_context_settings

_CONTEXT_PATHS = {"/api/settings/context", "/api/settings/context/"}
_FACTS_PATHS = {"/api/memories/facts", "/api/memories/facts/"}


def handle_contexto_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "context":
        return 200, {"ok": True, "settings": get_context_settings()}
    if len(parts) == 3 and parts[1] == "memories" and parts[2] == "facts":
        from app.storage import memory_facts
        return 200, {"ok": True, "facts": memory_facts.list_facts()}
    return None


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("JSON inválido.") from None


def _facts_post(payload: Any) -> tuple[int, dict[str, Any]]:
    from app.services import memory_kernel
    from app.storage import memory_facts

    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "Envie um objeto JSON."}
    operation = payload.get("operation")
    text = payload.get("text")
    fact_id = payload.get("id")
    if operation in ("save", "update"):
        clean = " ".join(str(text or "").split()) if isinstance(text, str) else ""
        if not clean:
            return 400, {"ok": False, "error": "Escreva o texto da memória."}
        if len(clean) > memory_facts.MAX_TEXT:
            return 400, {"ok": False, "error": f"A memória pode ter no máximo {memory_facts.MAX_TEXT} caracteres."}
    if operation in ("update", "delete"):
        live = memory_facts.get(fact_id) if isinstance(fact_id, str) else None
        if live is None or live.get("deleted_at"):
            return 400, {"ok": False, "error": "Memória não encontrada."}
    if operation == "save":
        result = memory_kernel.save_via_kernel(clean, kind="manual", session_id="", origin="window")
    elif operation == "update":
        result = memory_kernel.update_via_kernel(fact_id, clean, origin="window")
    elif operation == "delete":
        result = memory_kernel.delete_via_kernel(fact_id, origin="window")
    else:
        return 400, {"ok": False, "error": "Operação desconhecida: use save, update ou delete."}
    return (200 if result.get("ok") else 400), result


def handle_contexto_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path in _CONTEXT_PATHS:
        try:
            payload = _json(body)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            values = payload.get("settings", payload) if isinstance(payload, dict) else payload
            return 200, {"ok": True, "settings": set_context_settings(values)}
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    if path in _FACTS_PATHS:
        try:
            return _facts_post(_json(body))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    return None
