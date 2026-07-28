from __future__ import annotations

import json
from typing import Any

from app.storage.runtime_settings import get_llm_settings, set_llm_provider


def handle_settings_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "llm":
        default = getattr(handler.settings, "llm_provider", "gemini")
        return 200, get_llm_settings(default)
    return None


def handle_settings_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/settings/llm":
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except Exception:
        return 400, {"ok": False, "error": "JSON inválido."}

    provider = payload.get("llm_provider")
    if not provider:
        return 400, {"ok": False, "error": "Campo llm_provider é obrigatório."}

    try:
        set_llm_provider(str(provider))
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}

    default = getattr(handler.settings, "llm_provider", "gemini")
    data = get_llm_settings(default)
    data["ok"] = True
    return 200, data
