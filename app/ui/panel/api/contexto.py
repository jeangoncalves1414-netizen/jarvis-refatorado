"""Rotas do contexto situacional, das memórias com fonte e do Home Assistant (fases contexto 1, 2 e 3).

GET/POST /api/settings/context.
GET/POST /api/memories/facts (salvar, editar e remover passam pelo Kernel, origem janela).
GET/POST /api/settings/home-assistant e /test.
GET /api/home/entities e POST /api/home/action (passam pelo Kernel, origem janela).
"""
from __future__ import annotations

import json
from typing import Any

from app.storage.contexto_settings import (
    get_context_settings,
    set_context_settings,
    home_assistant_public,
    set_home_assistant,
)

_CONTEXT_PATHS = {"/api/settings/context", "/api/settings/context/"}
_FACTS_PATHS = {"/api/memories/facts", "/api/memories/facts/"}
_HA_SETTINGS_PATHS = {"/api/settings/home-assistant", "/api/settings/home-assistant/"}
_HA_TEST_PATHS = {"/api/settings/home-assistant/test", "/api/settings/home-assistant/test/"}
_HOME_ACTION_PATHS = {"/api/home/action", "/api/home/action/"}


def handle_contexto_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "context":
        return 200, {"ok": True, "settings": get_context_settings()}
    if len(parts) == 3 and parts[1] == "memories" and parts[2] == "facts":
        from app.storage import memory_facts
        return 200, {"ok": True, "facts": memory_facts.list_facts()}
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "home-assistant":
        return 200, {"ok": True, "settings": home_assistant_public()}
    if len(parts) == 3 and parts[1] == "home" and parts[2] == "entities":
        from app.services import home_assistant as ha
        if not ha.is_configured():
            return 200, {"ok": True, "configured": False, "entities": []}
        from app.agent.action_gateway import run_action
        outcome = run_action(
            "home",
            {"operation": "list_entities"},
            source="window:casa",
            user_text="Listar aparelhos da casa",
            origin="window",
        )
        if outcome.succeeded:
            data = outcome.result.data if outcome.result and outcome.result.data else {}
            entities = data.get("entities") or []
            return 200, {"ok": True, "configured": True, "entities": entities}
        msg = outcome.result.message if outcome.result else "Falha ao listar aparelhos."
        return 200, {"ok": False, "configured": True, "entities": [], "error": msg}
    return None


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("JSON inválido.") from None


def _facts_post(payload: Any, semantic=None) -> tuple[int, dict[str, Any]]:
    from app.services import memory_kernel
    from app.storage import memory_facts

    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "Envie um objeto JSON."}
    operation = payload.get("operation")
    text = payload.get("text")
    fact_id = payload.get("id")
    if operation in ("delete", "delete_many"):
        ids = [fact_id] if operation == "delete" else payload.get("ids")
        if not isinstance(ids, list) or not ids or not all(isinstance(i, str) and i for i in ids):
            return 400, {"ok": False, "error": "Selecione memórias válidas."}
        live_ids = {f["id"] for f in memory_facts.list_facts()}
        if any(i not in live_ids for i in ids):
            return 400, {"ok": False, "error": "Memória não encontrada."}
        removed = []
        for item in dict.fromkeys(ids):
            result = memory_kernel.delete_via_kernel(item, origin="window")
            if not result.get("ok"):
                return 400, {**result, "error": f"{len(removed)} removida(s). {result.get('error', 'Falha ao remover.')}", "ids": removed}
            removed.append(item)
            if semantic is not None:
                semantic.delete_where("user_memory", {"fact_id": item})
        return 200, {**result, "ids": removed}
    if operation in ("save", "update"):
        clean = " ".join(str(text or "").split()) if isinstance(text, str) else ""
        if not clean:
            return 400, {"ok": False, "error": "Escreva o texto da memória."}
        if len(clean) > memory_facts.MAX_TEXT:
            return 400, {"ok": False, "error": f"A memória pode ter no máximo {memory_facts.MAX_TEXT} caracteres."}
    if operation == "update":
        live = memory_facts.get(fact_id) if isinstance(fact_id, str) else None
        if live is None or live.get("deleted_at"):
            return 400, {"ok": False, "error": "Memória não encontrada."}
    if operation == "save":
        result = memory_kernel.save_via_kernel(clean, kind="manual", session_id="", origin="window")
    elif operation == "update":
        result = memory_kernel.update_via_kernel(fact_id, clean, origin="window")
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
            from app.ui.panel import server
            return _facts_post(_json(body), getattr(server._orchestrator, "semantic_memory", None))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    if path in _HA_SETTINGS_PATHS:
        try:
            payload = _json(body)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        try:
            values = payload.get("settings", payload) if isinstance(payload, dict) else payload
            return 200, {"ok": True, "settings": set_home_assistant(values)}
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    if path in _HA_TEST_PATHS:
        from app.services import home_assistant as ha
        return 200, ha.ping()
    if path in _HOME_ACTION_PATHS:
        try:
            return _home_action_post(_json(body))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
    return None


def _home_action_post(payload: Any) -> tuple[int, dict[str, Any]]:
    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "Envie um objeto JSON."}
    operation = str(payload.get("operation") or "").strip().lower()
    entity = str(payload.get("entity") or "").strip()
    if not operation:
        return 400, {"ok": False, "error": "Informe a operação."}
    if not entity and operation != "list_entities":
        return 400, {"ok": False, "error": "Informe o aparelho."}
    from app.services import home_assistant as ha
    if not ha.is_configured():
        return 200, {"ok": False, "configured": False, "message": "Desligado: Home Assistant não configurado."}
    from app.agent.action_gateway import run_action
    args: dict[str, Any] = {"operation": operation}
    if entity:
        args["entity"] = entity
    for key in ("brightness", "temperature", "area"):
        if key in payload and payload[key] is not None:
            args[key] = payload[key]
    user_text = f"Casa: {operation} em {entity}" if entity else f"Casa: {operation}"
    outcome = run_action(
        "home",
        args,
        source="window:casa",
        user_text=user_text,
        origin="window",
    )
    action_dict = outcome.action.public_dict() if outcome.action else None
    if outcome.pending:
        return 200, {
            "ok": False,
            "pending": True,
            "pending_action_id": outcome.action.id if outcome.action else None,
            "message": "Aguardando aprovação na Central de Execuções.",
            "action": action_dict,
        }
    if outcome.succeeded:
        msg = outcome.result.message if outcome.result and outcome.result.message else "Ação concluída."
        return 200, {
            "ok": True,
            "message": msg,
            "action": action_dict,
        }
    msg = outcome.result.message if outcome.result and outcome.result.message else "Falha ao executar a ação."
    return 200, {
        "ok": False,
        "message": msg,
        "action": action_dict,
    }
