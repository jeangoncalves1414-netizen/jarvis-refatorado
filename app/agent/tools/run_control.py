"""Read actual execution receipts and cancel a request in this conversation."""
from __future__ import annotations

from app.core.actions import redact
from app.core.runs import current_run
from .base import BaseTool, ToolResult


class RunControlTool(BaseTool):
    name = "run_control"
    description = (
        "Consulta pedidos em andamento e resultados reais desta conversa: 'o que está em andamento?', "
        "'quanto falta para terminar?' e 'qual o progresso?'. Não são tarefas do organizador pessoal. "
        "Use status antes de cancel; cancel exige run_id exato. "
        "Cancelar impede novas etapas, mas não desfaz ações nem garante interrupção imediata."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["status", "cancel"]},
            "run_id": {"type": "string", "description": "ID exato retornado por status; obrigatório para cancel."},
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def execute(self, args, context=None):
        action = args.get("action", "status")
        if not isinstance(action, str) or action not in {"status", "cancel"}:
            return ToolResult(False, "Use status ou cancel.")
        active = current_run.get()
        if not active:
            return ToolResult(False, "Abra uma conversa para consultar ou cancelar seus pedidos.")
        store, own_id = active
        own = store.run_details(own_id)
        session = own["run"]["session_id"] if own else None
        if not session:
            return ToolResult(False, "Esta execução não está vinculada a uma conversa.")
        target = args.get("run_id")
        if target is not None and (not isinstance(target, str) or not target.strip() or len(target) > 100):
            return ToolResult(False, "Informe um run_id válido retornado por status.")
        if action == "cancel" and not target:
            return ToolResult(False, "Consulte status e informe o run_id do pedido que deseja cancelar.")
        if target:
            detail = store.run_details(target)
            if target == own_id or not detail or detail["run"]["session_id"] != session:
                return ToolResult(False, "Pedido não disponível nesta conversa; este comando não pode cancelar a si mesmo.")
            if action == "cancel":
                try:
                    run = store.cancel_run(target)
                except (KeyError, ValueError) as exc:
                    return ToolResult(False, str(exc))
                message = ("Pedido cancelado." if run["status"] == "cancelled" else
                           "Cancelamento solicitado; aguardando a etapa em andamento retornar.")
                return ToolResult(True, f"{target}: {message} Etapas já executadas não foram desfeitas.",
                                  {"run_id": target, "status": run["status"]})
            runs = [detail["run"]]
        else:
            # Query active states separately so recent finished requests cannot hide an older active one.
            ongoing = [run for status in ("running", "awaiting_confirmation", "cancel_requested")
                       for run in store.run_page(session_id=session, status=status, limit=20)["runs"]]
            recent = store.run_page(session_id=session, limit=6)["runs"]
            runs = list({run["id"]: run for run in ongoing + recent if run["id"] != own_id}.values())
        if not runs:
            return ToolResult(True, "Nenhum outro pedido registrado nesta conversa.", {"results": []})
        results = []
        for run in runs:
            detail = store.run_details(run["id"])
            if not detail:
                continue
            current = detail["run"]
            # Execution budgets are ceilings, not the number of steps left to finish.
            progress = current.get("progress")
            if isinstance(progress, dict):
                progress = {key: progress[key] for key in ("phase", "step", "wait_remaining", "wait_total", "summary")
                            if key in progress}
            results.append({
                "id": current["id"], "status": current["status"],
                "progress": progress, "summary": current.get("result_summary"),
                "actions": [{key: item.get(key) for key in ("tool_name", "status", "result_summary")}
                            for item in detail["actions"][-5:]],
            })
        labels = {"running": "em andamento", "awaiting_confirmation": "aguardando aprovação",
                  "cancel_requested": "cancelamento solicitado", "cancelled": "cancelado",
                  "succeeded": "encerrado", "failed": "falhou", "interrupted": "interrompido"}
        lines = [f"{item['id']}: {labels.get(item['status'], item['status'])}." for item in results]
        return ToolResult(True, "Pedidos desta conversa (estado consultado agora):\n" + "\n".join(lines)
                          + "\nO total de etapas restantes e o prazo total não são conhecidos. "
                            "wait_remaining mede apenas a espera atual, em segundos; step é a etapa atual.",
                          {"results": redact(results, limit=500)})
