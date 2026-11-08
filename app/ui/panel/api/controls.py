"""Controles do PC (brilho, bloqueio de tela, volume, mídia) para a janela do painel.

A rota não toca o sistema: monta o pedido e o entrega ao Action Kernel (``action_gateway.run_action``), que
classifica o risco, registra a ação na Central de Execuções e só então chama a ferramenta
``system_control``. A resposta traz o resultado real da ferramenta, nunca um sucesso presumido.
O modelo de IA não participa; os controles funcionam com o provedor fora do ar.
"""
from __future__ import annotations

import json
from typing import Any

from app.agent.action_gateway import run_action
from app.agent.tools.system_control import parse_brightness_level

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
    outcome = run_action(
        "system_control", arguments, source=CONTROLS_SOURCE,
        user_text=f"Controles do PC: {operation}", run_mode=CONTROLS_RUN_MODE,
    )
    action, result = outcome.action, outcome.result
    if outcome.cancelled:
        return 409, {"ok": False, "error": "O pedido foi cancelado antes de concluir."}
    if outcome.crashed:
        return 500, {"ok": False, "error": "Falha ao executar o controle.", "action": action.public_dict() if action else None}
    if action is None:
        return 500, {"ok": False, "error": "A ação não foi registrada; nada foi executado."}
    if outcome.pending:
        # Operações desta janela são de risco baixo/observação; se o mapa de risco mudar, nada roda sem aprovação.
        return 202, {"ok": False, "pending": True, "error": "Esta operação exige confirmação na Central de Execuções.", "action": action.public_dict()}
    succeeded = outcome.succeeded
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
