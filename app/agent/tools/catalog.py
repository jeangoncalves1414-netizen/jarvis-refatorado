"""Central safety catalog for built-in tools.

Tool implementations stay small; the registration boundary owns the policy
metadata consumed by the Action Kernel.  Unknown/plugin tools intentionally
fall back to their own metadata (or the conservative BaseTool default).
"""
from __future__ import annotations

from typing import Any

from app.core.actions import ActionRisk, ToolMetadata


def _by_operation(**levels: tuple[str, ...]) -> tuple[tuple[str, ActionRisk], ...]:
    """Agrupa operações por risco: ``observe=(...), low=(...), high=(...)``."""
    return tuple((operation, risk) for risk, operations in levels.items() for operation in operations)


def _open_app_target_risk(operation: str, arguments: dict[str, Any]) -> ActionRisk:
    """``open`` só é low para app conhecido; nome livre ou caminho de arquivo pede aprovação.

    O caminho de marcadores envia o nome em "command"; as chamadas nativas, em "app_name".
    """
    if operation != "open":
        return "observe"
    from app.services.app_manager import is_known_app_target

    targets = [arguments[name] for name in ("app_name", "command") if name in arguments]
    known = bool(targets) and all(isinstance(t, str) and is_known_app_target(t) for t in targets)
    return "low" if known else "high"


TOOL_CATALOG: dict[str, ToolMetadata] = {
    "web_search": ToolMetadata(("web", "observe"), "observe"),
    # Ferramentas de controle têm risco por operação (ToolMetadata.risk_for).
    # Os nomes espelham o despacho de cada ferramenta; o que estiver fora do
    # mapa recebe "critical" e exige aprovação.
    "system_control": ToolMetadata(
        ("system", "control"), "critical",
        # O caminho de marcadores envia a operação em "command".
        operation_arguments=("action", "command"), default_operation="telemetry",
        operation_risks=_by_operation(
            observe=("telemetry", "list_processes", "get_brightness"),
            low=("open_app", "set_brightness", "lock_screen", "media_play_pause", "play", "pause", "media_next", "next",
                 "media_prev", "prev", "previous", "volume_up", "volume_down", "volume_mute"),
        ),
    ),
    "vision": ToolMetadata(("vision", "observe"), "observe"),
    "realtime": ToolMetadata(("realtime", "observe"), "observe"),
    "desktop_search": ToolMetadata(("desktop", "observe"), "observe"),
    # Só pede ao painel que abra uma janela do registro; não altera dados nem o sistema.
    "open_window": ToolMetadata(("ui", "window"), "observe"),
    "planning_workspace": ToolMetadata(("planning", "workspace"), "low", reversible=True),
    "timer": ToolMetadata(("timer", "productivity"), "low", reversible=True),
    "calendar": ToolMetadata(("calendar", "productivity"), "low", reversible=True),
    "notes": ToolMetadata(("notes", "productivity"), "low", reversible=True),
    "whiteboard_add_text": ToolMetadata(("whiteboard", "productivity"), "low", reversible=True),
    "whiteboard_add_image": ToolMetadata(("whiteboard", "productivity"), "low", reversible=True),
    "whiteboard_edit": ToolMetadata(("whiteboard", "productivity"), "low", reversible=True),
    "whiteboard_clear": ToolMetadata(("whiteboard", "productivity"), "high", requires_confirmation=True),
    "open_windows_app": ToolMetadata(
        ("desktop", "application"), "critical",
        operation_arguments=("action",), default_operation="open",
        operation_risks=_by_operation(observe=("list", "status"), low=("open",), high=("close",)),
        target_risk=_open_app_target_risk,
    ),
    # Módulos pessoais (AQ2). Ler é observe; gravar é low; apagar é high e pede aprovação.
    # A operação é a ação pedida; ação fora do mapa recebe "critical". O padrão de cada
    # ferramenta (``default_operation``) espelha o padrão do seu ``run``.
    "habit_tool": ToolMetadata(
        ("habits", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="list",
        operation_risks=_by_operation(
            observe=("list",),
            low=("create", "update", "check", "complete", "done", "uncheck", "undo"),
            high=("delete",),
        ),
        target_arguments=("name", "habit_id"),
        operation_effects=(
            ("list", "Apenas lê os hábitos; nada é alterado."),
            ("create", "Cria um hábito novo."),
            ("update", "Altera dias, horário ou itens de um hábito existente."),
            ("check", "Marca o hábito como concluído hoje."),
            ("complete", "Marca o hábito como concluído hoje."),
            ("done", "Marca o hábito como concluído hoje."),
            ("uncheck", "Desfaz a marcação de hoje do hábito."),
            ("undo", "Desfaz a marcação de hoje do hábito."),
            ("delete", "Remove o hábito."),
        ),
    ),
    "task_tool": ToolMetadata(
        ("tasks", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="list",
        operation_risks=_by_operation(
            observe=("list",),
            low=("create", "toggle", "complete", "done"),
            high=("delete",),
        ),
        target_arguments=("title", "task_id"),
        operation_effects=(
            ("list", "Apenas lê as tarefas pendentes; nada é alterado."),
            ("create", "Cria uma tarefa nova."),
            ("toggle", "Conclui a tarefa ou a reabre."),
            ("complete", "Conclui a tarefa ou a reabre."),
            ("done", "Conclui a tarefa ou a reabre."),
            ("delete", "Exclui a tarefa."),
        ),
    ),
    "finance_tool": ToolMetadata(
        ("finance", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="summary",
        operation_risks=_by_operation(
            observe=("summary", "list"),
            low=("add", "create"),
            high=("delete",),
        ),
        target_arguments=("description", "category", "trans_id"),
        operation_effects=(
            ("summary", "Apenas lê o resumo financeiro; nada é alterado."),
            ("list", "Apenas lê os lançamentos recentes; nada é alterado."),
            ("add", "Registra um lançamento de receita ou despesa."),
            ("create", "Registra um lançamento de receita ou despesa."),
            ("delete", "Exclui um lançamento financeiro."),
        ),
    ),
    "lifeos_tool": ToolMetadata(
        ("lifeos", "personal"), "critical",
        operation_arguments=("action", "command"), default_operation="summary",
        operation_risks=_by_operation(
            observe=("get_water", "list_habits", "summary", "motivate"),
            low=("add_water", "check_habit", "check", "uncheck_habit", "uncheck", "log_workout"),
        ),
        target_arguments=("habit_name", "workout_name"),
        operation_effects=(
            ("get_water", "Apenas lê o consumo de água de hoje; nada é alterado."),
            ("list_habits", "Apenas lê os hábitos do Life OS; nada é alterado."),
            ("summary", "Apenas lê o resumo do dia; nada é alterado."),
            ("motivate", "Apenas lê o resumo do dia para uma mensagem; nada é alterado."),
            ("add_water", "Soma a quantidade informada ao consumo de água de hoje."),
            ("check_habit", "Marca o hábito do Life OS como concluído hoje."),
            ("check", "Marca o hábito do Life OS como concluído hoje."),
            ("uncheck_habit", "Desmarca o hábito do Life OS de hoje."),
            ("uncheck", "Desmarca o hábito do Life OS de hoje."),
            ("log_workout", "Registra o treino de hoje e marca o hábito de treino."),
        ),
    ),
    "spotify": ToolMetadata(("media",), "low"),
    "clipboard": ToolMetadata(("clipboard",), "low"),
    "whatsapp": ToolMetadata(("messaging",), "high", requires_confirmation=True),
    "browser_agent": ToolMetadata(("browser", "automation"), "high", requires_confirmation=True),
    "file_manager": ToolMetadata(("files",), "high", requires_confirmation=True),
    "script_runner": ToolMetadata(("script", "system"), "critical", requires_confirmation=True),
    "hacker_mode": ToolMetadata(("script", "system"), "critical", requires_confirmation=True),
    "mobile_adb": ToolMetadata(("mobile", "automation"), "high", requires_confirmation=True),
    "kasa_control": ToolMetadata(("device", "automation"), "high", requires_confirmation=True),
    "workflow": ToolMetadata(("workflow",), "high", requires_confirmation=True),
}


def metadata_for(tool_name: str, fallback: ToolMetadata) -> ToolMetadata:
    return TOOL_CATALOG.get(tool_name, fallback)
