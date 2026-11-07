from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.core.control_plane import ControlPlanePolicy
from app.core.execution_receipts import ExecutionReceipts
from app.services.hacker_terminal import hacker_terminal
from app.ui.panel import server as panel_server
from app.ui.panel.server import PanelHandler, PanelServer


def _handler(origin: str = "", token: str = "", client: str = "127.0.0.1", host: str = "127.0.0.1:8000"):
    headers = {"Host": host}
    if origin:
        headers["Origin"] = origin
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return SimpleNamespace(headers=headers, client_address=(client, 9999))


def test_loopback_starts_without_token_and_rejects_foreign_origin() -> None:
    policy = ControlPlanePolicy(Settings())
    assert policy.authorize(_handler(), "/api/safe", "POST")[0] is True
    assert policy.authorize(_handler("https://evil.example"), "/api/safe", "GET")[1] == 403
    assert policy.authorize(_handler("http://evil.example", host="evil.example"), "/api/safe", "GET")[1] == 403
    assert "http://evil.example" not in policy.allowed_origins()


def test_lan_fails_closed_and_public_config_is_redacted() -> None:
    with pytest.raises(ValueError):
        ControlPlanePolicy(Settings(access_mode="lan", lan_enabled=True, trusted_origins=["http://phone"]))
    settings = Settings(access_mode="lan", lan_enabled=True, control_token="secret-value", trusted_origins=["http://phone"])
    assert "secret-value" not in str(settings.public_control_plane_config())
    policy = ControlPlanePolicy(settings)
    assert policy.authorize(_handler("http://phone"), "/api/safe", "POST")[1] == 401
    assert policy.authorize(_handler("http://phone", "secret-value"), "/api/safe", "POST")[0] is True


def test_receipts_are_bound_single_use_and_expire(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("app.core.execution_receipts.time.time", lambda: clock[0])
    store = ExecutionReceipts(ttl_seconds=1)
    receipt = store.issue("desktop", "script:python", "print('ok')")
    assert not store.consume(receipt, "desktop", "script:python", "print('changed')")
    receipt = store.issue("desktop", "script:python", "print('ok')")
    assert store.consume(receipt, "desktop", "script:python", "print('ok')")
    assert not store.consume(receipt, "desktop", "script:python", "print('ok')")
    expired = store.issue("desktop", "script:python", "print('ok')")
    clock[0] = 102.0
    assert not store.consume(expired, "desktop", "script:python", "print('ok')")


@pytest.fixture
def panel_http_server(monkeypatch: pytest.MonkeyPatch):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    previous_settings = PanelHandler.settings
    PanelHandler.settings = Settings(host="127.0.0.1", port=httpd.server_address[1])
    panel_server.receipts._items.clear()
    hacker_terminal.pending_commands.clear()
    hacker_terminal.audit_logs.clear()
    hacker_terminal.policy_audit.clear()
    hacker_terminal.policy_mode = "ask_every_time"
    calls: list[object] = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="mocked output", stderr="")

    monkeypatch.setattr("subprocess.run", fake_run)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"127.0.0.1:{httpd.server_address[1]}", calls
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
        PanelHandler.settings = previous_settings
        panel_server.receipts._items.clear()
        hacker_terminal.pending_commands.clear()
        hacker_terminal.audit_logs.clear()
        hacker_terminal.policy_audit.clear()
        hacker_terminal.policy_mode = "ask_every_time"


def _post(address: str, path: str, payload: dict, headers: dict | None = None) -> tuple[int, dict]:
    connection = http.client.HTTPConnection(address, timeout=3)
    try:
        connection.request("POST", path, json.dumps(payload), {"Content-Type": "application/json", **(headers or {})})
        response = connection.getresponse()
        return response.status, json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()


def test_script_run_requires_bound_single_use_receipt_over_http(panel_http_server) -> None:
    address, calls = panel_http_server
    code = "print('harmless')"
    status, body = _post(address, "/api/script/run", {"language": "python", "code": code})
    assert status == 403 and not body["ok"] and calls == []
    status, body = _post(address, "/api/script/authorize", {"language": "python", "code": code, "confirmed": True})
    assert status == 200 and body["ok"]
    status, _ = _post(address, "/api/script/run", {"language": "python", "code": code, "receipt": body["receipt"] + "altered"})
    assert status == 403 and calls == []
    status, body = _post(address, "/api/script/authorize", {"language": "python", "code": code, "confirmed": True})
    receipt = body["receipt"]
    status, body = _post(address, "/api/script/run", {"language": "python", "code": code, "receipt": receipt})
    assert status == 200 and body["ok"] and len(calls) == 1
    status, _ = _post(address, "/api/script/run", {"language": "python", "code": code, "receipt": receipt})
    assert status == 403 and len(calls) == 1


def test_hacker_http_cannot_bypass_receipts_with_force_or_direct_policy(panel_http_server, monkeypatch: pytest.MonkeyPatch) -> None:
    address, _ = panel_http_server
    executions: list[str] = []
    monkeypatch.setattr(hacker_terminal, "_run_command_subprocess", lambda command, risk_level, approved: executions.append(command) or {"ok": True, "status": "executed", "command": command})
    status, body = _post(address, "/api/hacker/policy", {"mode": "direct_execution"})
    assert status == 200 and body["ok"] and hacker_terminal.policy_audit[-1].actor == "local-desktop"
    status, body = _post(address, "/api/hacker/execute", {"command": "echo harmless", "force": True})
    assert status == 200 and body["status"] == "pending_approval" and executions == []
    status, receipt_body = _post(address, "/api/hacker/approve", {"cmd_id": body["cmd_id"]})
    assert status == 200 and receipt_body["ok"]
    status, body = _post(address, "/api/hacker/execute", {"command": "echo harmless", "receipt": receipt_body["receipt"], "force": True})
    assert status == 200 and body["status"] == "executed" and executions == ["echo harmless"]


def test_lan_mode_explicitly_disables_the_unauthenticated_websocket_port() -> None:
    settings = Settings(host="0.0.0.0", port=8000, access_mode="lan", lan_enabled=True, control_token="test-token", trusted_origins=["http://192.168.1.10:8000"])
    assert not PanelServer(settings)._websocket_enabled()
    assert not PanelServer(Settings(host="0.0.0.0"))._websocket_enabled()
    assert PanelServer(Settings(host="127.0.0.1"))._websocket_enabled()


def test_run_routes_keep_control_plane_boundary(panel_http_server, tmp_path, monkeypatch):
    from app.storage.action_store import ActionStore
    from app.ui.panel.api import runs
    store = ActionStore(tmp_path / "runs.sqlite3")
    monkeypatch.setattr(runs, "action_store", store)
    run = store.create_run(session_id="fixture-session", mode="general")
    address, calls = panel_http_server
    connection = http.client.HTTPConnection(address, timeout=3)
    try:
        connection.request("GET", "/api/runs")
        response = connection.getresponse()
        assert response.status == 200
        assert json.loads(response.read())["runs"][0]["id"] == run.id
        connection.request("POST", f"/api/runs/{run.id}/cancel", "{}", {"Origin": "https://evil.example", "Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 403
        response.read()
        assert store.run_details(run.id)["run"]["status"] == "running"
        status, body = _post(address, f"/api/runs/{run.id}/cancel", {})
        assert status == 200 and body["run"]["status"] == "cancel_requested"
        assert calls == []
    finally:
        connection.close()
        store._runtime_lock.close()


@pytest.fixture
def bridge(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.services.device_bridge import DeviceBridgeService
    state_path = tmp_path / "bridge.json"
    original_init = DeviceBridgeService.__init__
    monkeypatch.setattr(DeviceBridgeService, "__init__", lambda self, *_args, **_kwargs: original_init(self, state_path))
    service = DeviceBridgeService()
    code = service.get_pairing_code()
    tokens = {device_id: service.register_device(device_id, kind="controller", pairing_code=code)["device_token"] for device_id in ("desktop", "phone")}
    return service, tokens


def _device_ids(service) -> list[str]:
    return [device["id"] for device in service.get_status()["devices"]]


def test_local_owner_removes_another_device_and_gains_nothing_else(panel_http_server, bridge) -> None:
    address, _ = panel_http_server
    service, tokens = bridge
    status, body = _post(address, "/api/bridge", {"action": "command", "target_id": "phone", "command": "turn_on", "source": "desktop"})
    assert status == 400 and not body["ok"]
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone"}, {"Origin": f"http://{address}"})
    assert status == 200 and body == {"ok": True, "removed": "phone"}
    assert _device_ids(service) == ["desktop"]
    assert not service.heartbeat("phone", tokens["phone"])["ok"]
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone"})
    assert status == 400 and "não encontrado" in body["error"]


def test_loopback_removal_with_foreign_origin_is_refused(panel_http_server, bridge) -> None:
    address, _ = panel_http_server
    service, _ = bridge
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone"}, {"Origin": "https://evil.example"})
    assert status == 403 and body["error"] == "Origem não confiável."
    assert _device_ids(service) == ["desktop", "phone"]


def test_network_removal_still_requires_control_token_and_own_credential(panel_http_server, bridge) -> None:
    address, _ = panel_http_server
    service, tokens = bridge
    port = int(address.rsplit(":", 1)[1])
    # In LAN mode every request is a network principal, even from 127.0.0.1.
    PanelHandler.settings = Settings(host="127.0.0.1", port=port, access_mode="lan", lan_enabled=True, control_token="test-token", trusted_origins=[f"http://{address}"])
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone"})
    assert status == 401 and body["error"] == "Autenticação obrigatória."
    authorized = {"Authorization": "Bearer test-token"}
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone"}, authorized)
    assert status == 400 and "credencial do próprio dispositivo" in body["error"]
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone", "device_token": tokens["desktop"]}, authorized)
    assert status == 400 and "credencial do próprio dispositivo" in body["error"]
    assert _device_ids(service) == ["desktop", "phone"]
    status, body = _post(address, "/api/bridge", {"action": "remove", "device_id": "phone", "device_token": tokens["phone"]}, authorized)
    assert status == 200 and body == {"ok": True, "removed": "phone"}
    assert _device_ids(service) == ["desktop"]
