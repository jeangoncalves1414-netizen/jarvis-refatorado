from __future__ import annotations

from unittest.mock import patch

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.open_windows_app import OpenWindowsAppTool
from app.agent.tools.system_control import SystemControlTool
from app.agent.tools.workflow import WorkflowTool, validate_recipe
from app.core.actions import ActionRecord, ToolMetadata
from app.storage.action_store import ActionStore
from app.core.actions import pending_action_broker


def _executor(tmp_path, metadata: ToolMetadata, calls: list[str]) -> ActionExecutor:
    return ActionExecutor(
        frozenset({"fixture"}), ToolCallGuardrailController(),
        lambda name, args, user: calls.append(name) or ToolResult(True, "feito"),
        metadata_for=lambda name: metadata,
        store=ActionStore(tmp_path / "actions.jsonl"), source="test",
    )


def test_high_risk_is_proposed_without_execution(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="high", requires_confirmation=True), calls)
    message = executor.execute("fixture", {"target": "x"}, "faça")
    assert "exige confirmação" in message
    assert calls == []
    assert executor.store.list()[0].status == "awaiting_confirmation"


def test_approved_high_risk_callback_executes_once(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="high", requires_confirmation=True), calls)
    executor.execute("fixture", {}, "faça")
    action = executor.store.list()[0]
    executor.store.transition(action.id, "authorized")
    callback = pending_action_broker.take(action.id)
    assert callback is not None and callback() == "feito"
    assert calls == ["fixture"]
    assert executor.store.get(action.id).status == "succeeded"
    assert pending_action_broker.take(action.id) is None


def test_observation_is_journaled_and_runs(tmp_path):
    calls: list[str] = []
    executor = _executor(tmp_path, ToolMetadata(default_risk="observe"), calls)
    assert executor.execute("fixture", {}, "observe") == "feito"
    assert calls == ["fixture"]
    assert executor.store.list()[0].status == "succeeded"


def test_store_rejects_invalid_transition(tmp_path):
    store = ActionStore(tmp_path / "actions.jsonl")
    item = store.create(ActionRecord.create(source="test", tool_name="x", metadata=ToolMetadata(), arguments={}, preview="x"))
    with pytest.raises(ValueError):
        store.transition(item.id, "succeeded")


def test_public_history_redacts_script_payload(tmp_path):
    item = ActionRecord.create(source="test", tool_name="x", metadata=ToolMetadata(), arguments={"script": "secret"}, preview="Executar script")
    assert "secret" not in str(item.public_dict())


def test_workflow_is_declarative_and_dry_run_only():
    tool = WorkflowTool()
    result = tool.execute({"recipe_id": "planejamento_semanal", "dry_run": True})
    assert result.ok and result.data["dry_run"] is True
    with pytest.raises(ValueError):
        validate_recipe({"name": "x", "capabilities": ["a"], "steps": [{"tool": "other"}]})


def _control_executor(tmp_path, tools: dict) -> ActionExecutor:
    """Executor com o catálogo real e as ferramentas reais; o sistema fica sempre mockado."""
    return ActionExecutor(
        frozenset(tools), ToolCallGuardrailController(),
        lambda name, args, user: tools[name].execute(args),
        metadata_for=TOOL_CATALOG.get,
        store=ActionStore(tmp_path / "actions.jsonl"), source="test",
    )


def test_closing_app_waits_for_approval_and_runs_once_after_it(tmp_path):
    tool = OpenWindowsAppTool()
    executor = _control_executor(tmp_path, {"open_windows_app": tool})
    with patch("subprocess.Popen") as popen, \
         patch.object(tool.app_manager, "close_app", return_value=(True, "Aplicativo 'notepad' encerrado com sucesso.")) as close_app:
        message = executor.execute("open_windows_app", {"action": "close", "app_name": "notepad"}, "feche o bloco de notas")
        action = executor.last_action
        assert "exige confirmação" in message
        assert (action.risk, action.status) == ("high", "awaiting_confirmation")
        close_app.assert_not_called()

        executor.store.transition(action.id, "authorized")
        assert pending_action_broker.take(action.id)() == "Aplicativo 'notepad' encerrado com sucesso."
    close_app.assert_called_once_with("notepad")
    popen.assert_not_called()
    assert executor.store.get(action.id).status == "succeeded"


@pytest.mark.parametrize("operation", ["kill_process", "kill", "shutdown"])
def test_unrecognized_system_operation_waits_for_approval(tmp_path, operation):
    executor = _control_executor(tmp_path, {"system_control": SystemControlTool()})
    with patch("subprocess.Popen") as popen, \
         patch("app.agent.tools.system_control._press_media_key") as press, \
         patch("psutil.process_iter") as process_iter:
        message = executor.execute("system_control", {"action": operation, "app_name": "explorer"}, "mate o explorer")
    assert "exige confirmação" in message
    assert (executor.last_action.risk, executor.last_action.status) == ("critical", "awaiting_confirmation")
    popen.assert_not_called()
    press.assert_not_called()
    process_iter.assert_not_called()


@pytest.mark.parametrize(("operation", "message"), [
    ("volume_up", "Volume do sistema aumentado."),
    ("volume_mute", "Mute/Unmute do sistema alterado."),
    ("media_next", "Avançado para a próxima faixa no player ativo."),
])
def test_volume_and_media_run_without_approval(tmp_path, operation, message):
    executor = _control_executor(tmp_path, {"system_control": SystemControlTool()})
    with patch("subprocess.Popen") as popen, patch("app.agent.tools.system_control._press_media_key") as press:
        assert executor.execute("system_control", {"action": operation}, "ajuste o volume") == message
    press.assert_called_once()
    popen.assert_not_called()
    assert (executor.last_action.risk, executor.last_action.status) == ("low", "succeeded")


def test_opening_allowed_app_runs_without_approval(tmp_path):
    executor = _control_executor(tmp_path, {"system_control": SystemControlTool()})
    with patch("subprocess.Popen") as popen:
        executor.execute("system_control", {"action": "open_app", "app_name": "notepad"}, "abra o bloco de notas")
    popen.assert_called_once_with("notepad.exe", shell=False)
    assert (executor.last_action.risk, executor.last_action.status) == ("low", "succeeded")


def test_listing_processes_is_observation(tmp_path):
    executor = _control_executor(tmp_path, {"system_control": SystemControlTool()})
    with patch("subprocess.Popen") as popen, patch("psutil.process_iter", return_value=[]) as process_iter:
        executor.execute("system_control", {"action": "list_processes"}, "liste os processos")
    process_iter.assert_called_once()
    popen.assert_not_called()
    assert (executor.last_action.risk, executor.last_action.status) == ("observe", "succeeded")


@pytest.mark.parametrize("approved", [False, True])
def test_typed_failure_is_never_recorded_as_success(tmp_path, approved):
    executor = ActionExecutor(
        None, ToolCallGuardrailController(),
        lambda *_: ToolResult(False, "Arquivo não encontrado."),
        metadata_for=lambda _: ToolMetadata(requires_confirmation=approved),
        store=ActionStore(tmp_path / "actions.jsonl"),
    )
    message = executor.execute("fixture", {}, "leia")
    action = executor.store.list()[0]
    if approved:
        executor.store.transition(action.id, "authorized")
        message = pending_action_broker.take(action.id)()
    assert message == "Arquivo não encontrado."
    assert executor.store.get(action.id).status == "failed"
