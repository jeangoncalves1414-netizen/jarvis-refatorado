"""Central safety catalog for built-in tools.

Tool implementations stay small; the registration boundary owns the policy
metadata consumed by the Action Kernel.  Unknown/plugin tools intentionally
fall back to their own metadata (or the conservative BaseTool default).
"""
from __future__ import annotations

from app.core.actions import ActionRisk, ToolMetadata


def _by_operation(**levels: tuple[str, ...]) -> tuple[tuple[str, ActionRisk], ...]:
    """Agrupa operações por risco: ``observe=(...), low=(...), high=(...)``."""
    return tuple((operation, risk) for risk, operations in levels.items() for operation in operations)


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
            observe=("telemetry", "list_processes"),
            low=("open_app", "media_play_pause", "play", "pause", "media_next", "next",
                 "media_prev", "prev", "previous", "volume_up", "volume_down", "volume_mute"),
        ),
    ),
    "vision": ToolMetadata(("vision", "observe"), "observe"),
    "realtime": ToolMetadata(("realtime", "observe"), "observe"),
    "desktop_search": ToolMetadata(("desktop", "observe"), "observe"),
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
