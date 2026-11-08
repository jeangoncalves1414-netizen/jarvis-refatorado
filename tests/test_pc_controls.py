from __future__ import annotations

import json
import subprocess
from unittest.mock import patch

import pytest

from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import GENERAL_TOOL_NAMES, registry
from app.agent.tools.system_control import SystemControlTool
from app.storage.action_store import ActionStore
from app.ui.panel.api.controls import CONTROL_OPERATIONS, handle_controls_post

# Todo o acesso ao sistema é simulado: subprocess.run e as teclas de mídia nunca chegam ao Windows.


def _completed(returncode: int = 0, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture
def journal(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "controls.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    yield store
    if store._runtime_lock:
        store._runtime_lock.close()


def _post(payload) -> tuple[int, dict]:
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    result = handle_controls_post("/api/controls/run", body, None)
    assert result is not None
    return result


# --- risco por operação -------------------------------------------------------------------------

@pytest.mark.parametrize(("operation", "risk"), [
    ("get_brightness", "observe"),
    ("set_brightness", "low"),
    ("lock_screen", "low"),
    ("volume_up", "low"),
    ("volume_down", "low"),
    ("volume_mute", "low"),
    ("media_play_pause", "low"),
    ("media_next", "low"),
    ("media_prev", "low"),
    ("GET_BRIGHTNESS", "observe"),
    ("brightness", "critical"),
    ("unlock_screen", "critical"),
    ("shutdown", "critical"),
])
def test_risk_per_operation(operation, risk):
    assert TOOL_CATALOG["system_control"].risk_for({"action": operation}) == risk


def test_every_panel_operation_is_low_or_observe():
    metadata = TOOL_CATALOG["system_control"]
    assert {metadata.risk_for({"action": operation}) for operation in CONTROL_OPERATIONS} <= {"observe", "low"}


def test_new_operations_are_declared_to_the_model():
    parameters = SystemControlTool().parameters
    assert {"get_brightness", "set_brightness", "lock_screen"} <= set(parameters["properties"]["action"]["enum"])
    assert parameters["properties"]["level"]["maximum"] == 100


# --- ferramenta: brilho -------------------------------------------------------------------------

@pytest.mark.parametrize("level", [-1, 101, 1000, "abc", "", "50; calc", "5 0", True, False, 50.5, None, [50], {"v": 1}])
def test_invalid_brightness_is_rejected_without_touching_the_system(level):
    with patch("subprocess.run") as run, patch("subprocess.Popen") as popen:
        result = SystemControlTool().execute({"action": "set_brightness", "level": level})
    assert result.ok is False
    assert "inválido" in result.message
    run.assert_not_called()
    popen.assert_not_called()


def test_missing_brightness_level_is_rejected():
    with patch("subprocess.run") as run:
        result = SystemControlTool().execute({"action": "set_brightness"})
    assert result.ok is False
    run.assert_not_called()


@pytest.mark.parametrize(("level", "expected"), [(0, 0), (40, 40), (100, 100), ("75", 75), (30.0, 30)])
def test_set_brightness_runs_fixed_powershell_without_shell(level, expected):
    with patch("subprocess.run", return_value=_completed(0)) as run:
        result = SystemControlTool().execute({"action": "set_brightness", "level": level})
    assert result.ok is True
    assert result.data["brightness"] == expected
    argv = run.call_args.args[0]
    assert isinstance(argv, list) and argv[0] == "powershell.exe"
    assert run.call_args.kwargs["shell"] is False
    assert "WmiMonitorBrightnessMethods" in argv[-1]
    assert f"Brightness=[byte]{expected}" in argv[-1]


@pytest.mark.parametrize("failure", [
    _completed(1),
    _completed(3),
    FileNotFoundError("powershell.exe"),
    subprocess.TimeoutExpired("powershell.exe", 15),
    OSError("indisponível"),
])
def test_unsupported_brightness_returns_ok_false_with_reason(failure):
    side_effect = failure if isinstance(failure, BaseException) else None
    with patch("subprocess.run", return_value=None if side_effect else failure, side_effect=side_effect):
        changed = SystemControlTool().execute({"action": "set_brightness", "level": 50})
    with patch("subprocess.run", return_value=None if side_effect else failure, side_effect=side_effect):
        read = SystemControlTool().execute({"action": "get_brightness"})
    for result in (changed, read):
        assert result.ok is False
        assert "não suportado" in result.message
        assert result.data == {"supported": False}


def test_get_brightness_reads_the_value_from_windows():
    with patch("subprocess.run", return_value=_completed(0, "62\r\n")) as run:
        result = SystemControlTool().execute({"action": "get_brightness"})
    assert result.ok is True
    assert result.data["brightness"] == 62
    assert "62%" in result.message
    assert run.call_args.kwargs["shell"] is False
    assert "WmiMonitorBrightness " in run.call_args.args[0][-1]


@pytest.mark.parametrize("output", ["", "abc", "250", "-5"])
def test_get_brightness_with_unexpected_output_is_not_a_success(output):
    with patch("subprocess.run", return_value=_completed(0, output)):
        result = SystemControlTool().execute({"action": "get_brightness"})
    assert result.ok is False


# --- ferramenta: bloqueio de tela ---------------------------------------------------------------

def test_lock_screen_uses_rundll32_without_shell():
    with patch("subprocess.run", return_value=_completed(0)) as run:
        result = SystemControlTool().execute({"action": "lock_screen"})
    assert result.ok is True
    assert run.call_args.args[0] == ["rundll32.exe", "user32.dll,LockWorkStation"]
    assert run.call_args.kwargs["shell"] is False


@pytest.mark.parametrize("failure", [_completed(1), FileNotFoundError("rundll32.exe"), subprocess.TimeoutExpired("rundll32.exe", 15)])
def test_lock_screen_failure_is_reported(failure):
    side_effect = failure if isinstance(failure, BaseException) else None
    with patch("subprocess.run", return_value=None if side_effect else failure, side_effect=side_effect):
        result = SystemControlTool().execute({"action": "lock_screen"})
    assert result.ok is False


# --- endpoint: Action Kernel --------------------------------------------------------------------

def test_endpoint_creates_an_action_record_with_the_real_result(journal):
    with patch("subprocess.run", return_value=_completed(0)) as run:
        status, payload = _post({"operation": "set_brightness", "level": 35})
    assert status == 200 and payload["ok"] is True
    assert payload["data"]["brightness"] == 35
    assert payload["action"]["status"] == "succeeded"
    assert payload["action"]["risk"] == "low"
    run.assert_called_once()

    actions = journal.list()
    assert len(actions) == 1
    assert (actions[0].tool_name, actions[0].status, actions[0].risk) == ("system_control", "succeeded", "low")
    assert actions[0].source == "panel:controls"
    assert actions[0].run_id

    runs = journal.run_page(limit=5)["runs"]
    assert len(runs) == 1 and runs[0]["id"] == actions[0].run_id
    assert runs[0]["status"] == "succeeded"


def test_endpoint_records_a_failed_action_when_brightness_is_unsupported(journal):
    with patch("subprocess.run", return_value=_completed(1)):
        status, payload = _post({"operation": "set_brightness", "level": 50})
    assert status == 200
    assert payload["ok"] is False
    assert "não suportado" in payload["error"]
    assert payload["action"]["status"] == "failed"
    assert [action.status for action in journal.list()] == ["failed"]
    assert journal.run_page(limit=5)["runs"][0]["status"] == "failed"


def test_endpoint_reads_brightness_as_an_observation(journal):
    with patch("subprocess.run", return_value=_completed(0, "80")):
        status, payload = _post({"operation": "get_brightness"})
    assert status == 200 and payload["data"]["brightness"] == 80
    assert (payload["action"]["risk"], payload["action"]["status"]) == ("observe", "succeeded")


def test_endpoint_locks_the_screen_through_the_kernel(journal):
    with patch("subprocess.run", return_value=_completed(0)) as run:
        status, payload = _post({"operation": "lock_screen"})
    assert status == 200 and payload["ok"] is True
    assert run.call_args.args[0] == ["rundll32.exe", "user32.dll,LockWorkStation"]
    assert payload["action"]["risk"] == "low"
    assert len(journal.list()) == 1


@pytest.mark.parametrize("operation", ["volume_up", "volume_down", "volume_mute", "media_play_pause", "media_next", "media_prev"])
def test_endpoint_volume_and_media_use_simulated_keys(journal, operation):
    with patch("app.agent.tools.system_control._press_media_key") as press, patch("subprocess.run") as run:
        status, payload = _post({"operation": operation})
    assert status == 200 and payload["ok"] is True
    press.assert_called_once()
    run.assert_not_called()
    assert [(action.risk, action.status) for action in journal.list()] == [("low", "succeeded")]


@pytest.mark.parametrize("level", [-1, 101, "abc", True, 12.5, None])
def test_endpoint_rejects_invalid_brightness_before_the_kernel(journal, level):
    with patch("subprocess.run") as run:
        status, payload = _post({"operation": "set_brightness", "level": level})
    assert status == 400 and payload["ok"] is False
    run.assert_not_called()
    assert journal.list() == []


@pytest.mark.parametrize("payload", [{"operation": "shutdown"}, {"operation": "kill_process"}, {"operation": 7}, {}, {"action": "lock_screen"}])
def test_endpoint_rejects_unknown_operations(journal, payload):
    with patch("subprocess.run") as run, patch("app.agent.tools.system_control._press_media_key") as press:
        status, body = _post(payload)
    assert status == 400 and body["ok"] is False
    run.assert_not_called()
    press.assert_not_called()
    assert journal.list() == []


@pytest.mark.parametrize("body", [b"not json", b"[1]", b"\xff"])
def test_endpoint_rejects_malformed_json(journal, body):
    status, payload = _post(body)
    assert status == 400 and payload["ok"] is False


def test_endpoint_ignores_other_paths():
    assert handle_controls_post("/api/controls", b"{}", None) is None
    assert handle_controls_post("/api/actions/x/approve", b"{}", None) is None


def test_controls_route_is_registered_in_the_panel_server():
    from app.ui.panel import server

    assert server.handle_controls_post is handle_controls_post


def test_open_window_tool_can_open_the_controls_window_without_params():
    from app.agent.tools.open_window import OpenWindowTool

    opened = OpenWindowTool().execute({"window_id": "pc-controls"})
    assert opened.ok is True
    assert opened.data["ui_window"] == {"window_id": "pc-controls", "params": {}}
    # A janela não aceita parâmetros: nada de nível de brilho vindo do modelo.
    rejected = OpenWindowTool().execute({"window_id": "pc-controls", "params": {"level": 10}})
    assert rejected.ok is False and "ui_window" not in rejected.data


def test_agent_can_use_the_new_operations_through_the_registered_tool():
    assert "system_control" in GENERAL_TOOL_NAMES
    metadata = registry.get_tool_metadata("system_control")
    assert metadata is not None
    assert metadata.risk_for({"action": "lock_screen"}) == "low"
