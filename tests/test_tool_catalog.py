from __future__ import annotations

import pytest

from app.agent.tools.catalog import TOOL_CATALOG, metadata_for
from app.agent.tools.open_windows_app import OpenWindowsAppTool
from app.agent.tools.system_control import SystemControlTool
from app.core.actions import ToolMetadata


def test_catalog_has_explicit_policy_for_privileged_builtin_tools():
    for name in ("file_manager", "browser_agent", "whatsapp", "script_runner", "hacker_mode", "mobile_adb"):
        metadata = TOOL_CATALOG[name]
        assert metadata.default_risk in {"high", "critical"}
        assert metadata.requires_confirmation is True


def test_unknown_tool_keeps_its_own_metadata():
    fallback = ToolMetadata(("plugin",), "low")
    assert metadata_for("future_plugin", fallback) is fallback


@pytest.mark.parametrize(("tool", "arguments", "risk"), [
    ("system_control", {"action": "telemetry"}, "observe"),
    ("system_control", {"action": "list_processes"}, "observe"),
    ("system_control", {}, "observe"),
    ("system_control", {"action": "volume_up"}, "low"),
    ("system_control", {"action": "VOLUME_MUTE"}, "low"),
    ("system_control", {"action": "media_play_pause"}, "low"),
    ("system_control", {"action": "next"}, "low"),
    ("system_control", {"action": "open_app", "app_name": "notepad"}, "low"),
    ("system_control", {"command": "volume_down"}, "low"),
    ("system_control", {"action": "kill_process", "app_name": "explorer"}, "critical"),
    ("system_control", {"action": "shutdown"}, "critical"),
    ("system_control", {"action": None}, "critical"),
    ("system_control", {"command": "kill_process"}, "critical"),
    ("open_windows_app", {"action": "list"}, "observe"),
    ("open_windows_app", {"action": "status", "app_name": "chrome"}, "observe"),
    ("open_windows_app", {"action": "open", "app_name": "chrome"}, "low"),
    ("open_windows_app", {"app_name": "chrome"}, "low"),
    ("open_windows_app", {"command": "chrome"}, "low"),
    ("open_windows_app", {"action": "close", "app_name": "chrome"}, "high"),
    ("open_windows_app", {"action": " Close ", "app_name": "chrome"}, "high"),
    ("open_windows_app", {"action": "kill", "app_name": "chrome"}, "critical"),
    ("open_windows_app", {"action": ""}, "critical"),
])
def test_control_tools_classify_risk_by_operation(tool, arguments, risk):
    assert TOOL_CATALOG[tool].risk_for(arguments) == risk


@pytest.mark.parametrize(("name", "parameters"), [
    ("system_control", SystemControlTool().parameters),
    ("open_windows_app", OpenWindowsAppTool.parameters),
])
def test_every_declared_control_operation_has_explicit_risk(name, parameters):
    for operation in parameters["properties"]["action"]["enum"]:
        assert TOOL_CATALOG[name].risk_for({"action": operation}) != "critical", operation


def test_tool_without_operation_map_keeps_its_default_risk():
    assert ToolMetadata(("x",), "high").risk_for({"action": "list"}) == "high"


def test_invalid_operation_risk_is_rejected():
    with pytest.raises(ValueError):
        ToolMetadata(operation_arguments=("action",), operation_risks=(("list", "safe"),))
