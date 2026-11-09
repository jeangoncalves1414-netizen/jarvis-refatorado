"""Endpoints de API para gerenciamento de Persona e prévias de Briefing."""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from app.agent.personas import (
    get_persona,
    update_persona,
    reset_persona,
)


def handle_persona_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Manipula requisições GET em /api/persona."""
    if len(parts) < 2 or parts[0] != "api" or parts[1] != "persona":
        return None

    try:
        if len(parts) == 2:
            return 200, {"ok": True, "persona": get_persona()}

        sub = parts[2]
        if sub == "preview-morning":
            from app.services.briefing import generate_morning_briefing
            text = generate_morning_briefing()
            return 200, {"ok": True, "text": text}

        if sub == "preview-evening":
            from app.services.briefing import generate_evening_debriefing
            text = generate_evening_debriefing()
            return 200, {"ok": True, "text": text}

        return 404, {"ok": False, "error": f"Endpoint sub-recurso '{sub}' não encontrado."}
    except Exception as exc:
        return 500, {"ok": False, "error": f"Erro interno ao consultar persona: {exc}"}


def handle_persona_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Manipula requisições POST em /api/persona."""
    clean_path = urlsplit(path).path.rstrip("/")
    if clean_path != "/api/persona":
        return None

    try:
        raw = body.decode("utf-8") if body else "{}"
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return 400, {"ok": False, "error": f"JSON inválido: {exc}"}

    try:
        if payload.get("action") == "reset":
            restored = reset_persona()
            return 200, {"ok": True, "persona": restored}

        # Aceita payload direto ou aninhado em "persona"
        updates = payload.get("persona", payload)
        if not isinstance(updates, dict):
            return 400, {"ok": False, "error": "Formato de payload inválido."}

        updated = update_persona(updates)
        return 200, {"ok": True, "persona": updated}
    except Exception as exc:
        return 400, {"ok": False, "error": f"Erro ao atualizar persona: {exc}"}
