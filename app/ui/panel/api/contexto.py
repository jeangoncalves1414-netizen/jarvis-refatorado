"""Rotas do contexto situacional (fase contexto 1).

GET/POST /api/settings/context.
"""
from __future__ import annotations

import json
from typing import Any

from app.storage.contexto_settings import get_context_settings, set_context_settings

_CONTEXT_PATHS = {"/api/settings/context", "/api/settings/context/"}


def handle_contexto_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "context":
        return 200, {"ok": True, "settings": get_context_settings()}
    return None


def handle_contexto_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path in _CONTEXT_PATHS:
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"ok": False, "error": "JSON inválido."}
        try:
            values = payload.get("settings", payload) if isinstance(payload, dict) else payload
            return 200, {"ok": True, "settings": set_context_settings(values)}
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    return None
