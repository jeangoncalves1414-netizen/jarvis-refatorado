"""Ponto de entrada único do Action Kernel para pedidos que não vêm de um turno do modelo (AQ1, C10).

Rotas diretas do servidor (controles do PC, navegador automatizado, scripts aprovados no chat,
terminal) entregam o pedido aqui em vez de chamar a ferramenta. O gateway abre um Run, monta o
``ActionExecutor`` limitado à ferramenta pedida e devolve o registro da ação com o resultado real.
Risco, aprovação e histórico são os mesmos do chat: o que exige aprovação fica aguardando na
Central, e nada roda sem registro.

Pedidos de conversa (chat e voz) passam pelo orquestrador; a origem do pedido (``chat`` ou
``voice``) fica em ``current_origin`` e vai para a origem de cada ação registrada no turno.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.core.actions import ActionRecord
from app.core.runs import REQUEST_ORIGINS, RunCancelled, current_run

DirectExecute = Callable[[dict[str, Any]], ToolResult]


def request_origin(value: Any) -> str:
    """Origem enviada pelo cliente; valor desconhecido vira ``chat``."""
    return value if isinstance(value, str) and value in REQUEST_ORIGINS else "chat"


@dataclass
class ActionOutcome:
    action: ActionRecord | None
    result: ToolResult | None
    cancelled: bool = False
    crashed: bool = False

    @property
    def pending(self) -> bool:
        return self.action is not None and self.action.status == "awaiting_confirmation"

    @property
    def succeeded(self) -> bool:
        return (
            self.action is not None and self.action.status == "succeeded"
            and self.result is not None and self.result.ok
        )


def run_action(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    source: str,
    user_text: str,
    run_mode: str = "direct",
    execute: DirectExecute | None = None,
    context: dict[str, Any] | None = None,
    confirmed_by: str | None = None,
    origin: str = "window",
) -> ActionOutcome:
    """Executa ``tool_name`` pelo Action Kernel e devolve a ação registrada e o resultado.

    ``execute`` substitui a chamada ao registro de ferramentas quando a rota já tem a sua própria
    execução (script, terminal). ``confirmed_by`` só deve ser usado quando a rota já validou uma
    confirmação explícita da usuária (recibo de uso único): a ação é registrada, marcada como
    autorizada com esse texto e executada; sem ele, ações de risco alto ou crítico ficam aguardando
    aprovação na Central.
    """
    # Resolvidos na chamada para que testes e o servidor usem o armazenamento vigente.
    import app.storage.action_store as store_module
    from app.agent.tools.catalog import TOOL_CATALOG
    from app.agent.tools.registry import registry

    store = store_module.action_store
    captured: dict[str, ToolResult] = {}

    def call(name: str, args: dict, _user_text: str) -> ToolResult:
        result = execute(args) if execute is not None else registry.execute_tool(name, args, context=context)
        captured["result"] = result
        return result

    def metadata(name: str):
        return registry.get_tool_metadata(name) or TOOL_CATALOG.get(name)

    outcome = ActionOutcome(None, None)
    # Rotas diretas nascem de uma janela do painel, salvo quando a rota diz outra origem (C6).
    run = store.create_run(session_id=source, mode=run_mode, source=source, origin=origin)
    token = current_run.set((store, run.id))
    try:
        executor = ActionExecutor(
            frozenset({tool_name}), ToolCallGuardrailController(), call,
            metadata_for=metadata, store=store, source=source,
        )
        try:
            if confirmed_by is None:
                executor.execute(tool_name, arguments, user_text)
            else:
                # Sem user_text a proposta não entra no broker: a confirmação já veio do recibo.
                action = executor.propose(tool_name, arguments)
                if action.status in ("proposed", "awaiting_confirmation"):
                    executor.last_action = store.transition(
                        action.id, "authorized", result_summary=confirmed_by, expected_status=action.status,
                    )
                executor.execute_authorized(action.id, tool_name, arguments, user_text)
        except RunCancelled:
            outcome.cancelled = True
        except Exception:
            outcome.crashed = True
        outcome.action = executor.last_action
        outcome.result = captured.get("result")
        return outcome
    finally:
        try:
            store.finish_run(run.id, failed=not (outcome.succeeded or outcome.pending))
        finally:
            current_run.reset(token)
