from __future__ import annotations

import os
import tempfile

import pytest
from types import SimpleNamespace

from app.agent.prompts import build_runtime_identity_context
from app.config import load_settings
from app.storage import runtime_settings
from app.ui.panel.api.settings import handle_settings_get, handle_settings_post
from app.services.llm import LLMService


@pytest.fixture
def isolated_routes(monkeypatch: pytest.MonkeyPatch):
    previous_provider = os.environ.get("LLM_PROVIDER")
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(runtime_settings, "DATA_DIR", tmp)
        monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", os.path.join(tmp, "runtime.json"))
        for name in (
            "GEMINI_API_KEY", "GEMINI_API_KEYS", "GROQ_API_KEY", "GROQ_API_KEYS",
            "OXYY_API_KEY", "OXYY_API_KEYS", "FISH_API_KEY", "FISH_API_KEYS",
        ):
            monkeypatch.delenv(name, raising=False)
        yield
        if previous_provider is None:
            os.environ.pop("LLM_PROVIDER", None)
        else:
            os.environ["LLM_PROVIDER"] = previous_provider


def test_explicit_oxyy_primary_and_catalog_model_does_not_switch_provider(isolated_routes, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    monkeypatch.setenv("OXYY_API_KEY", "test-oxyy")
    runtime_settings.set_llm_provider("groq")
    runtime_settings.set_oxyy_models({"chat": "gemini-2.5-flash"})
    route = runtime_settings.get_ai_settings()["routes"]["chat"]
    assert route["primary"]["provider"] == "groq"
    assert route["effective"]["provider"] == "groq"
    assert route["effective"]["model"] == os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    runtime_settings.set_ai_routes({"chat": {"provider": "oxyy", "model": "gemini-2.5-flash"}})
    route = runtime_settings.get_ai_settings()["routes"]["chat"]
    assert route["primary"]["provider"] == "oxyy"
    assert route["effective"]["provider"] == "oxyy"
    assert route["effective"]["model"] == "gemini-2.5-flash"


def test_missing_primary_exposes_deterministic_fallback(isolated_routes, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    runtime_settings.set_llm_provider("groq")
    route = runtime_settings.get_ai_settings()["routes"]["chat"]
    assert route["primary"]["provider"] == "groq"
    assert route["fallback_used"] is True
    assert route["effective"]["provider"] == "gemini"
    assert "sem chave" in route["reason"]


def test_all_providers_unavailable_has_no_effective_route(isolated_routes):
    runtime_settings.set_llm_provider("groq")
    route = runtime_settings.get_ai_settings()["routes"]["chat"]
    assert route["effective"] is None
    assert route["configured"] is False
    assert route["fallback_used"] is False


def test_persisted_route_survives_resolve(isolated_routes, monkeypatch):
    monkeypatch.setenv("OXYY_API_KEY", "test-oxyy")
    runtime_settings.set_ai_routes({"chat": {"provider": "oxyy", "model": "custom-chat"}})
    route = runtime_settings.resolve_ai_routes()["chat"]
    assert route["primary"] == {"provider": "oxyy", "model": "custom-chat"}
    assert route["effective"]["provider"] == "oxyy"


def test_persisted_route_survives_load_settings(isolated_routes, monkeypatch):
    monkeypatch.setenv("OXYY_API_KEY", "test-oxyy")
    runtime_settings.set_ai_routes({"chat": {"provider": "oxyy", "model": "custom-chat"}})
    settings = load_settings()
    assert settings.llm_provider == "oxyy"


def test_runtime_identity_context_is_factual_and_secret_free(isolated_routes):
    text = build_runtime_identity_context({
        "effective": {"provider": "oxyy", "model": "gemini-2.5-flash"},
        "fallback_used": False,
        "reason": "Rota principal configurada.",
    })
    assert "Motor ativo: oxyy; modelo: gemini-2.5-flash" in text
    assert "GPT-4" not in text
    assert "api_key" not in text.lower()


def test_llm_uses_effective_route_model(isolated_routes, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq")
    runtime_settings.set_ai_routes({"chat": {"provider": "groq", "model": "custom-route-model"}})
    settings = SimpleNamespace(groq_model="old-model", llm_model="old-gemini", oxyy_chat_model="old-oxyy", oxyy_model="old-oxyy")
    service = LLMService(settings)
    assert service._effective_chat_model("groq") == "custom-route-model"


def test_settings_api_aggregate_and_legacy_contract(isolated_routes, monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "super-secret-test-key")
    handler = type("Handler", (), {"settings": type("Settings", (), {"llm_provider": "groq", "tts_provider": "edge", "stt_provider": "groq"})()})()
    status, payload = handle_settings_get(["api", "settings", "ai"], handler)
    assert status == 200 and "routes" in payload
    assert "super-secret" not in str(payload)
    status, payload = handle_settings_get(["api", "settings", "llm"], handler)
    assert status == 200
    assert payload["effective_provider"] == "groq"
    status, payload = handle_settings_post(
        "/api/settings/ai",
        b'{"routes":{"chat":{"provider":"gemini","model":"gemini-2.5-flash"}}}',
        handler,
    )
    assert status == 200
    assert payload["routes"]["chat"]["primary"]["provider"] == "gemini"
