"""Integrações com estado real (O1) e modelo que respondeu de fato após troca (O2)."""
from __future__ import annotations

import pytest

from app.agent.run_tracking import background_run
from app.core import capability_health as health_module
from app.core.capability_health import capability_health, failure_reason, reachable_from, record_tool_result, track_model_call
from app.core.runs import RunCancelled, current_run
from app.storage.action_store import ActionStore
from app.ui.panel.api import capabilities, mission_control


@pytest.fixture(autouse=True)
def clean_health():
    capability_health.clear()
    yield
    capability_health.clear()


@pytest.fixture
def journal(tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "health.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    yield store
    if store._runtime_lock:
        store._runtime_lock.close()


class FakeModels:
    def _effective_chat_model(self, provider):
        return f"{provider}-modelo"

    @track_model_call()
    def generate(self, fail_primary=True):
        try:
            return self._gemini(fail_primary)
        except Exception:
            return self._groq()

    @track_model_call("gemini")
    def _gemini(self, fail):
        if fail:
            raise RuntimeError("429 RESOURCE_EXHAUSTED key=sk-segredo-123")
        return "gemini"

    @track_model_call("groq")
    def _groq(self):
        return "groq"

    @track_model_call("gemini")
    def internal_fallback(self):
        try:
            raise ConnectionError("down")
        except Exception:
            return self._groq()

    @track_model_call()
    def ask(self):
        try:
            return self._gemini(True)
        except Exception as exc:
            return f"Erro ao acessar: {exc}"

    @track_model_call("gemini")
    def cancelled(self):
        raise RunCancelled("parou")


def test_failure_reason_never_copies_raw_message():
    reason = failure_reason(RuntimeError("401 invalid api key sk-segredo-123"))
    assert reason == "Chave recusada pelo provedor." and "sk-" not in reason
    assert failure_reason(RuntimeError("429 quota")) == "Limite de uso do provedor (429)."
    assert failure_reason(TimeoutError()) == "O provedor não respondeu a tempo."
    assert failure_reason(ValueError("algo")) == "Erro do provedor (ValueError)."


def test_fallback_records_who_answered_and_why(journal):
    with background_run(mode="general", source="conversation", origin="chat"):
        run_id = current_run.get()[1]
        assert FakeModels().generate() == "groq"
    chat = capability_health.get("chat")
    assert (chat["provider"], chat["model"]) == ("groq", "groq-modelo")
    assert chat["fallback"]["from"] == "gemini" and chat["fallback"]["to"] == "groq"
    assert chat["fallback"]["reason"] == "Limite de uso do provedor (429)."
    assert reachable_from(chat) is True and chat["last_failure_provider"] == "gemini"
    assert "sk-segredo" not in str(chat)
    events = [e for e in journal.run_details(run_id)["events"] if e["kind"] == "fallback"]
    assert events and "groq (groq-modelo) respondeu no lugar de gemini" in events[0]["summary"]


def test_primary_success_has_no_fallback():
    assert FakeModels().generate(fail_primary=False) == "gemini"
    chat = capability_health.get("chat")
    assert chat["provider"] == "gemini" and chat["fallback"] is None and chat["last_failure_at"] is None


def test_internal_fallback_inside_provider_call_is_detected():
    assert FakeModels().internal_fallback() == "groq"
    chat = capability_health.get("chat")
    assert chat["provider"] == "groq" and chat["fallback"]["from"] == "gemini"
    assert chat["fallback"]["reason"] == "Sem conexão com o provedor."


def test_exception_already_handled_by_caller_is_not_a_provider_failure():
    try:
        raise KeyError("da ferramenta")
    except KeyError:
        assert FakeModels().generate(fail_primary=False) == "gemini"
    assert capability_health.get("chat")["fallback"] is None


def test_entry_point_that_swallows_the_error_still_records_failure():
    assert FakeModels().ask().startswith("Erro")
    chat = capability_health.get("chat")
    assert chat["last_success_at"] is None and chat["last_failure_provider"] == "gemini"
    assert reachable_from(chat) is False


def test_cancellation_is_not_recorded_as_provider_failure():
    with pytest.raises(RunCancelled):
        FakeModels().cancelled()
    assert capability_health.get("chat") == {}


def test_tool_results_feed_integration_health():
    record_tool_result("spotify", False, "Spotify não abriu.")
    assert reachable_from(capability_health.get("spotify")) is False
    record_tool_result("spotify", True)
    assert reachable_from(capability_health.get("spotify")) is True
    record_tool_result("web_search", True)
    assert capability_health.get("web_search") == {}


class _Bridge:
    devices: list | Exception = []

    def get_status(self):
        if isinstance(self.devices, Exception):
            raise self.devices
        return {"devices": self.devices}


@pytest.fixture
def offline_world(monkeypatch):
    """Sem chaves, sem bibliotecas opcionais, sem npx e sem dispositivos."""
    for name in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "COMPOSIO_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(capabilities, "_has_module", lambda name: False)
    monkeypatch.setattr(capabilities.shutil, "which", lambda name: None)
    monkeypatch.setattr("app.agent.tools.mcp_tool._load_servers", lambda: {})
    monkeypatch.setattr("app.services.device_bridge.DeviceBridgeService", lambda *a, **k: _Bridge())
    routes = {key: {"configured": False, "reason": "sem chave", "effective": None} for key in ("chat", "tts", "stt", "image")}
    monkeypatch.setattr("app.storage.runtime_settings.resolve_ai_routes", lambda *a, **k: routes)
    _Bridge.devices = []
    yield routes


def _by_id(items):
    return {item["id"]: item for item in items}


def test_integrations_show_off_with_reason_for_what_is_missing(offline_world):
    items = _by_id(capabilities.build_capabilities())
    assert {"chat", "tts", "stt", "image", "vision", "devices", "spotify", "whatsapp", "telegram", "kasa", "mcp", "composio", "calendar"} <= set(items)
    for key in ("composio", "kasa", "mcp", "telegram", "whatsapp", "devices", "chat"):
        assert items[key]["status"] == "off", key
        assert items[key]["reason"].startswith("Desligado"), key
    assert "python-kasa" in items["kasa"]["reason"]
    assert "COMPOSIO_API_KEY" in items["composio"]["reason"]
    assert items["calendar"]["status"] == "configured" and items["calendar"]["reachable"] is None


def test_configured_capability_becomes_healthy_or_degraded_from_real_calls(offline_world, monkeypatch):
    offline_world["chat"] = {"configured": True, "reason": "Rota principal configurada.", "effective": {"provider": "gemini", "model": "g"}}
    assert _by_id(capabilities.build_capabilities())["chat"]["status"] == "configured"
    FakeModels().generate()
    chat = _by_id(capabilities.build_capabilities())["chat"]
    assert chat["status"] == "healthy" and chat["provider"] == "groq" and chat["fallback"]["from"] == "gemini"
    FakeModels().ask()
    assert _by_id(capabilities.build_capabilities())["chat"]["status"] == "degraded"


def test_devices_are_never_healthy_with_zero_or_read_error(offline_world, tmp_path, monkeypatch):
    store = ActionStore(tmp_path / "mc.sqlite3")
    monkeypatch.setattr(mission_control, "action_store", store)
    try:
        snapshot = mission_control.build_mission_snapshot()
        bridge = next(item for item in snapshot["components"] if item["id"] == "bridge")
        assert bridge["status"] == "off" and snapshot["summary"]["devices"] == 0
        _Bridge.devices = OSError("disco")
        snapshot = mission_control.build_mission_snapshot()
        bridge = next(item for item in snapshot["components"] if item["id"] == "bridge")
        assert bridge["status"] == "unavailable" and snapshot["summary"]["devices_error"]
        assert _by_id(snapshot["capabilities"])["devices"]["status"] == "unavailable"
        _Bridge.devices = [{"id": "p", "connected": False}]
        bridge = next(item for item in mission_control.build_mission_snapshot()["components"] if item["id"] == "bridge")
        assert bridge["status"] == "degraded"
        _Bridge.devices = [{"id": "p", "connected": True}]
        snapshot = mission_control.build_mission_snapshot()
        assert next(item for item in snapshot["components"] if item["id"] == "bridge")["status"] == "healthy"
        assert snapshot["health_since"] == health_module.capability_health.started_at
    finally:
        if store._runtime_lock:
            store._runtime_lock.close()
