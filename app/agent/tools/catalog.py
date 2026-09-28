"""Central safety catalog for built-in tools.

Tool implementations stay small; the registration boundary owns the policy
metadata consumed by the Action Kernel.  Unknown/plugin tools intentionally
fall back to their own metadata (or the conservative BaseTool default).
"""
from __future__ import annotations

from app.core.actions import ToolMetadata


TOOL_CATALOG: dict[str, ToolMetadata] = {
    "web_search": ToolMetadata(("web", "observe"), "observe"),
    "system_control": ToolMetadata(("system", "observe"), "observe"),
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
    "open_windows_app": ToolMetadata(("desktop", "application"), "low"),
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
