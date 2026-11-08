"""Controles do PC (brilho, bloqueio de tela, volume, mídia) para a janela do painel.

A rota não toca o sistema: monta o pedido e o entrega ao Action Kernel (ActionExecutor), que
classifica o risco, registra a ação na Central de Execuções e só então chama a ferramenta
``system_control``. A resposta traz o resultado real da ferramenta, nunca um sucesso presumido.
O modelo de IA não participa; os controles funcionam com o provedor fora do ar.
"""
from __future__ import annotations

import json
from typing import Any

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.system_control import parse_brightness_level
from app.core.runs import RunCancelled, current_run

CONTROLS_SOURCE = "panel:controls"
CONTROLS_RUN_MODE = "controls"

# Operações aceitas pela janela. Qualquer outra é recusada antes de chegar ao Action Kernel.
CONTROL_OPERATIONS = frozenset({
    "get_brightness", "set_brightness", "lock_screen",
    "volume_up", "volume_down", "volume_mute",
    "media_play_pause", "media_next", "media_prev",
})


def _bad_request(message: str) -> tuple[int, dict[str, Any]]:
    return 400, {"ok": False, "error": message}


def _run_control(operation: str, arguments: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    # Resolvidos na chamada para que testes e o servidor usem o armazenamento vigente.
    import app.storage.action_store as store_module
    from app.agent.tools.registry import registry

    store = store_module.action_store
    captured: dict[str, ToolResult] = {}

    def execute(name: str, args: dict, _user_text: str) -> ToolResult:
        result = registry.execute_tool(name, args)
        captured["result"] = result
        return result

    run = store.create_run(session_id=CONTROLS_SOURCE, mode=CONTROLS_RUN_MODE)
    token = current_run.set((store, run.id))
    failed = True
    try:
        executor = ActionExecutor(
            frozenset({"system_control"}), ToolCallGuardrailController(), execute,
            metadata_for=registry.get_tool_metadata, store=store, source=CONTROLS_SOURCE,
        )
        try:
            executor.execute("system_control", arguments, f"Controles do PC: {operation}")
        except RunCancelled:
            return 409, {"ok": False, "error": "O pedido foi cancelado antes de concluir."}
        except Exception:
            action = executor.last_action
            return 500, {"ok": False, "error": "Falha ao executar o controle.", "action": action.public_dict() if action else None}
        action = executor.last_action
        result = captured.get("result")
        if action is None:
            return 500, {"ok": False, "error": "A ação não foi registrada; nada foi executado."}
        if action.status == "awaiting_confirmation":
            # Operações desta janela são de risco baixo/observação; se o mapa de risco mudar, nada roda sem aprovação.
            failed = False
            return 202, {"ok": False, "pending": True, "error": "Esta operação exige confirmação na Central de Execuções.", "action": action.public_dict()}
        succeeded = action.status == "succeeded" and result is not None and result.ok
        failed = not succeeded
        payload: dict[str, Any] = {
            "ok": succeeded,
            "operation": operation,
            "message": result.message if result is not None else (action.result_summary or ""),
            "data": result.data if result is not None else {},
            "action": action.public_dict(),
        }
        if not succeeded:
            payload["error"] = payload["message"] or "A operação não foi concluída."
        return 200, payload
    finally:
        try:
            store.finish_run(run.id, failed=failed)
        finally:
            current_run.reset(token)


def handle_controls_post(path: str, body: bytes, _handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path.rstrip("/") != "/api/controls/run":
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError()
    except (UnicodeDecodeError, ValueError):
        return _bad_request("JSON inválido.")
    operation = payload.get("operation")
    if not isinstance(operation, str) or operation not in CONTROL_OPERATIONS:
        return _bad_request("Operação desconhecida. Use: " + ", ".join(sorted(CONTROL_OPERATIONS)) + ".")
    arguments: dict[str, Any] = {"action": operation}
    if operation == "set_brightness":
        level = parse_brightness_level(payload.get("level"))
        if level is None:
            return _bad_request("Brilho inválido: informe um número inteiro de 0 a 100.")
        arguments["level"] = level
    return _run_control(operation, arguments)
