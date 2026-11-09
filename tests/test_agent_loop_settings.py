from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import MagicMock

import pytest

from app.config import Settings
from app.storage import runtime_settings
from app.ui.panel.server import PanelHandler


@pytest.fixture
def base_url(isolated_lote6_data):
    PanelHandler.orchestrator = MagicMock()
    PanelHandler.settings = Settings(host="127.0.0.1", port=0)
    server = ThreadingHTTPServer(("127.0.0.1", 0), PanelHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    yield f"http://{host}:{port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def _get(url):
    with urllib.request.urlopen(url) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def _post(url, payload):
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def test_defaults_and_save(base_url, isolated_lote6_data):
    status, data = _get(f"{base_url}/api/settings/agent-loop")
    assert status == 200 and data["settings"] == {"mode": "auto", "max_steps": 8, "max_model_calls": 10, "auto_verify": True, "extract_memory_always": False}
    status, data = _post(f"{base_url}/api/settings/agent-loop", {"mode": "always", "max_steps": 20, "max_model_calls": 1, "auto_verify": False})
    assert status == 200 and data["settings"] == {"mode": "always", "max_steps": 20, "max_model_calls": 1, "auto_verify": False, "extract_memory_always": False}
    assert _get(f"{base_url}/api/settings/agent-loop")[1]["settings"]["mode"] == "always"
    saved = json.loads((isolated_lote6_data.root / "data" / "runtime_settings.json").read_text(encoding="utf-8"))
    assert saved["agent_loop"]["max_steps"] == 20


@pytest.mark.parametrize("payload, fragment", [
    ({"mode": "turbo"}, "Modo do agente inválido"),
    ({"max_steps": 0}, "de 1 a 20"),
    ({"max_steps": 21}, "de 1 a 20"),
    ({"max_steps": True}, "de 1 a 20"),
    ({"max_model_calls": 31}, "de 1 a 30"),
    ({"max_model_calls": "5"}, "de 1 a 30"),
    ({"auto_verify": "sim"}, "verificação automática"),
    ({"extra": 1}, "Campo desconhecido"),
])
def test_invalid_values_are_rejected_without_saving(base_url, payload, fragment):
    _post(f"{base_url}/api/settings/agent-loop", {"max_steps": 5})
    status, data = _post(f"{base_url}/api/settings/agent-loop", {**payload})
    assert status == 400 and data["ok"] is False and fragment in data["error"]
    assert runtime_settings.get_agent_loop_settings()["max_steps"] == 5


def test_invalid_json_and_corrupted_file_fall_back_to_defaults(base_url, isolated_lote6_data):
    req = urllib.request.Request(f"{base_url}/api/settings/agent-loop", data=b"{broken", headers={"Content-Type": "application/json"}, method="POST")
    with pytest.raises(urllib.error.HTTPError) as error:
        urllib.request.urlopen(req)
    assert error.value.code == 400
    path = isolated_lote6_data.root / "data" / "runtime_settings.json"
    path.write_text(json.dumps({"agent_loop": {"mode": "x", "max_steps": 99, "max_model_calls": -1, "auto_verify": "no"}}), encoding="utf-8")
    assert runtime_settings.get_agent_loop_settings() == {"mode": "auto", "max_steps": 8, "max_model_calls": 10, "auto_verify": True, "extract_memory_always": False}
