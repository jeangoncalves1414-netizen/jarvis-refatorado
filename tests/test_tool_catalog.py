from __future__ import annotations

import pytest

from app.agent.tools.catalog import TOOL_CATALOG, metadata_for
from app.agent.tools.open_windows_app import OpenWindowsAppTool
from app.agent.tools.system_control import SystemControlTool
from app.core.actions import ToolMetadata
from app.services.app_manager import AppManager


@pytest.fixture(autouse=True)
def _fake_registry(monkeypatch):
    """O registro do Windows nunca é lido: um único app instalado fictício."""
    monkeypatch.setattr(AppManager, "_scan_registry", lambda self: {"foo studio": r"C:\Apps\Foo\foo.exe"})


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
    # open é low só quando o alvo resolve por alias, comando do sistema, URI ou registro.
    ("open_windows_app", {"action": "open", "app_name": "calc.exe"}, "low"),
    ("open_windows_app", {"action": "open", "app_name": "slack"}, "low"),
    ("open_windows_app", {"action": "open", "app_name": "Foo Studio"}, "low"),
    ("open_windows_app", {"command": "bloco de notas"}, "low"),
    ("open_windows_app", {"action": "open", "app_name": "cmd /c echo x"}, "high"),
    ("open_windows_app", {"app_name": "notepad && calc"}, "high"),
    ("open_windows_app", {"command": "powershell -c whoami"}, "high"),
    ("open_windows_app", {"app_name": "chrome", "command": "cmd /c echo x"}, "high"),
    ("open_windows_app", {"action": "open", "app_name": ""}, "high"),
    ("open_windows_app", {"action": "open", "app_name": ["chrome"]}, "high"),
    ("open_windows_app", {"action": "open"}, "high"),
    ("open_windows_app", {"action": "status", "app_name": "cmd /c echo x"}, "observe"),
    ("open_windows_app", {"action": "close", "app_name": "cmd /c echo x"}, "high"),
])
def test_control_tools_classify_risk_by_operation(tool, arguments, risk):
    assert TOOL_CATALOG[tool].risk_for(arguments) == risk


def test_opening_arbitrary_existing_file_needs_approval(tmp_path):
    script = tmp_path / "script.bat"
    script.write_text("@echo off", encoding="utf-8")
    assert TOOL_CATALOG["open_windows_app"].risk_for({"action": "open", "app_name": str(script)}) == "high"


def test_target_risk_only_raises_and_fails_closed():
    base = {"operation_arguments": ("action",), "operation_risks": (("x", "high"),)}
    assert ToolMetadata(**base, target_risk=lambda _op, _args: "observe").risk_for({"action": "x"}) == "high"
    assert ToolMetadata(**base, target_risk=lambda _op, _args: "unknown").risk_for({"action": "x"}) == "critical"

    def broken(_op, _args):
        raise RuntimeError("falha ao resolver o alvo")
    assert ToolMetadata(**base, target_risk=broken).risk_for({"action": "x"}) == "critical"


@pytest.mark.parametrize(("name", "parameters"), [
    ("system_control", SystemControlTool().parameters),
    ("open_windows_app", OpenWindowsAppTool.parameters),
])
def test_every_declared_control_operation_has_explicit_risk(name, parameters):
    for operation in parameters["properties"]["action"]["enum"]:
        assert TOOL_CATALOG[name].risk_for({"action": operation}) != "critical", operation


def test_tool_without_operation_map_keeps_its_default_risk():
    assert ToolMetadata(("x",), "high").risk_for({"action": "list"}) == "high"


PERSONAL_TOOLS = ("habit_tool", "task_tool", "finance_tool", "lifeos_tool")


def _declared_operations(name):
    from app.agent.tools.registry import ToolRegistry

    return ToolRegistry().get_tool(name).parameters["properties"]["action"]["enum"]


@pytest.mark.parametrize("name", PERSONAL_TOOLS)
def test_personal_tools_have_catalog_metadata_for_every_declared_action(name):
    from app.agent.tools.registry import ToolRegistry

    assert name in TOOL_CATALOG
    registry_metadata = ToolRegistry().get_tool_metadata(name)
    assert registry_metadata is TOOL_CATALOG[name]
    for operation in _declared_operations(name):
        assert TOOL_CATALOG[name].risk_for({"action": operation}) != "critical", operation
        assert TOOL_CATALOG[name].effect_for({"action": operation}), operation


@pytest.mark.parametrize(("tool", "arguments", "risk"), [
    ("habit_tool", {}, "observe"),
    ("habit_tool", {"action": "list"}, "observe"),
    ("habit_tool", {"action": "create", "name": "Ler"}, "low"),
    ("habit_tool", {"action": "check", "habit_id": "h1"}, "low"),
    ("habit_tool", {"action": "delete", "habit_id": "h1"}, "high"),
    ("task_tool", {"action": "list"}, "observe"),
    ("task_tool", {"action": "create", "title": "Pagar conta"}, "low"),
    ("task_tool", {"action": "toggle", "task_id": "t1"}, "low"),
    ("task_tool", {"action": "delete", "task_id": "t1"}, "high"),
    ("finance_tool", {}, "observe"),
    ("finance_tool", {"action": "list"}, "observe"),
    ("finance_tool", {"action": "add", "amount": 50, "category": "Mercado"}, "low"),
    ("finance_tool", {"action": "delete", "trans_id": "f1"}, "high"),
    ("lifeos_tool", {}, "observe"),
    ("lifeos_tool", {"action": "get_water"}, "observe"),
    ("lifeos_tool", {"action": "add_water", "amount": 500}, "low"),
    ("lifeos_tool", {"action": "log_workout", "workout_name": "Pernas"}, "low"),
    # Ação desconhecida ou operação enviada pelo caminho de marcadores: fecha para o mais estrito.
    ("habit_tool", {"action": "apagar_tudo"}, "critical"),
    ("finance_tool", {"command": "texto livre"}, "critical"),
])
def test_personal_tools_classify_risk_by_operation(tool, arguments, risk):
    assert TOOL_CATALOG[tool].risk_for(arguments) == risk


def test_personal_tools_declare_target_and_effect():
    habit = TOOL_CATALOG["habit_tool"]
    assert habit.target_for({"action": "delete", "habit_id": "h1"}) == "h1"
    assert habit.target_for({"action": "delete", "name": "Ler", "habit_id": "h1"}) == "Ler"
    assert habit.effect_for({"action": "delete"}) == "Remove o hábito."
    assert TOOL_CATALOG["finance_tool"].target_for({"action": "add", "category": "Mercado"}) == "Mercado"
    assert TOOL_CATALOG["task_tool"].target_for({"action": "list"}) == ""
    assert "nada é alterado" in TOOL_CATALOG["lifeos_tool"].effect_for({"action": "summary"})
    assert TOOL_CATALOG["lifeos_tool"].effect_for({"action": "unknown"}) == ""
    # Ferramenta sem alvo/efeito declarados continua válida.
    assert ToolMetadata(("x",), "low").target_for({"name": "a"}) == ""
    assert ToolMetadata(("x",), "low").effect_for({"action": "a"}) == ""


def test_personal_tool_deletion_waits_for_approval_and_reads_do_not(tmp_path):
    from app.agent.action_executor import ActionExecutor
    from app.agent.tool_guardrails import ToolCallGuardrailController
    from app.agent.tools.base import ToolResult
    from app.storage.action_store import ActionStore

    store = ActionStore(tmp_path / "journal.sqlite3")
    calls = []
    executor = ActionExecutor(
        None, ToolCallGuardrailController(),
        lambda name, args, user: calls.append((name, args)) or ToolResult(True, "feito"),
        metadata_for=TOOL_CATALOG.get, store=store, source="test",
    )
    try:
        executor.execute("finance_tool", {"action": "summary"}, "saldo")
        assert (executor.last_action.risk, executor.last_action.status) == ("observe", "succeeded")
        executor.execute("finance_tool", {"action": "add", "amount": 50, "category": "Mercado"}, "gastei 50")
        assert (executor.last_action.risk, executor.last_action.status) == ("low", "succeeded")
        executor.execute("finance_tool", {"action": "delete", "trans_id": "f1"}, "apague")
        assert (executor.last_action.risk, executor.last_action.status) == ("high", "awaiting_confirmation")
        assert [args["action"] for _name, args in calls] == ["summary", "add"]
    finally:
        if store._runtime_lock:
            store._runtime_lock.close()


def test_invalid_operation_risk_is_rejected():
    with pytest.raises(ValueError):
        ToolMetadata(operation_arguments=("action",), operation_risks=(("list", "safe"),))
