from __future__ import annotations

import json
import re
import sys
from types import ModuleType, SimpleNamespace

import pytest

from app.agent import prompts
from app.services.voice import wake_word
from app.storage import runtime_settings
from app.ui.panel.api.settings import handle_settings_get, handle_settings_post

PROFILE_PATH = "/api/settings/agent-profile"
HANDLER = SimpleNamespace(settings=SimpleNamespace())


@pytest.fixture
def isolated_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime.json"))
    return tmp_path / "runtime.json"


@pytest.fixture
def vocabulary(monkeypatch):
    """Vocabulário falso do Vosk: o teste nunca carrega o modelo real."""
    known = {"ei", "assistente", "nova", "olá", "computador"}
    model = SimpleNamespace(vosk_model_find_word=lambda word: 1 if word in known else -1)
    monkeypatch.setattr(wake_word, "_get_model", lambda download=False: model)
    return known


def _post(payload) -> tuple[int, dict]:
    return handle_settings_post(PROFILE_PATH, json.dumps(payload).encode("utf-8"), HANDLER)


def test_default_profile_is_neutral(isolated_profile):
    profile = runtime_settings.get_agent_profile()
    assert profile["name"] == "Assistente"
    assert profile["wake_phrase"] == "ei assistente"
    assert profile["wake_phrase_custom"] is False
    for prompt in (
        prompts.build_function_calling_system_prompt("", [], ""),
        prompts.build_marker_agent_system_prompt("", []),
    ):
        lowered = prompt.lower()
        assert "você é assistente" in lowered
        for persona in ("jarvis", r"j\.a\.r\.v\.i\.s", "tony stark", "sir", "senhor", "britânic\\w*"):
            assert not re.search(rf"\b{persona}\b", lowered), persona


def test_custom_profile_prompt_uses_name_and_style(isolated_profile):
    custom = {"name": "Nova", "style": "Bem-humorada e direta.", "wake_phrase": ""}
    for prompt in (
        prompts.build_function_calling_system_prompt("", [], "", agent_profile=custom),
        prompts.build_marker_agent_system_prompt("", [], agent_profile=custom),
    ):
        assert "Você é Nova" in prompt
        assert "Bem-humorada e direta." in prompt
        assert "jarvis" not in prompt.lower()


def test_saved_profile_feeds_prompt_without_changing_tools(isolated_profile, vocabulary):
    tools = {"calendar", "file_manager", "web_search"}
    before = prompts.build_function_calling_system_prompt("", [], "", active_mode="chat", allowed_tool_names=tools)
    status, data = _post({"name": "Nova", "style": "Formal.", "wake_phrase": "olá computador"})
    assert status == 200 and data["ok"] is True
    after = prompts.build_function_calling_system_prompt("", [], "", active_mode="chat", allowed_tool_names=tools)
    assert "Você é Nova" in after and "Você é Assistente" in before
    tool_section = lambda text: text[text.index("## Modo ativo e ferramentas"):]
    assert tool_section(before) == tool_section(after)


def test_settings_api_round_trip(isolated_profile, vocabulary):
    status, data = handle_settings_get(["api", "settings", "agent-profile"], HANDLER)
    assert status == 200 and data["profile"]["name"] == "Assistente"

    status, data = _post({"name": "  Nova  ", "style": "", "wake_phrase": ""})
    assert status == 200
    assert data["profile"] == {
        "name": "Nova",
        "style": runtime_settings.DEFAULT_AGENT_STYLE,
        "wake_phrase": "ei nova",
        "wake_phrase_custom": False,
    }
    assert data["wake_phrase_check"]["supported"] is True
    stored = json.loads(isolated_profile.read_text(encoding="utf-8"))["agent_profile"]
    assert stored == {"name": "Nova", "style": runtime_settings.DEFAULT_AGENT_STYLE, "wake_phrase": ""}

    status, data = _post({"name": "Nova", "style": "Curta.", "wake_phrase": "  Olá   Computador "})
    assert status == 200
    status, data = handle_settings_get(["api", "settings", "agent-profile"], HANDLER)
    assert data["profile"]["wake_phrase"] == "olá computador"
    assert data["profile"]["wake_phrase_custom"] is True
    assert data["profile"]["style"] == "Curta."


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"name": "", "style": "x"}, "nome"),
        ({"name": "Nova", "wake_phrase": "ei nova 2"}, "só letras"),
        ({"name": "x" * 41}, "40"),
        ({"name": "Nova", "style": "y" * 2001}, "2000"),
        ({"name": "R2-D2", "wake_phrase": ""}, "derivar"),
    ],
)
def test_invalid_profile_is_rejected_and_not_saved(isolated_profile, vocabulary, payload, message):
    status, data = _post(payload)
    assert status == 400 and data["ok"] is False
    assert message in data["error"]
    assert not isolated_profile.exists()


def test_phrase_outside_vosk_vocabulary_is_rejected(isolated_profile, vocabulary):
    status, data = _post({"name": "Jarvis", "style": "", "wake_phrase": ""})
    assert status == 400
    assert data["wake_phrase_check"]["missing"] == ["jarvis"]
    assert "jarvis" in data["error"] and "não reconhece" in data["error"]
    assert runtime_settings.get_agent_profile()["name"] == "Assistente"

    # Nome fora do vocabulário funciona com uma frase personalizada reconhecida.
    status, data = _post({"name": "Jarvis", "style": "", "wake_phrase": "ei assistente"})
    assert status == 200 and data["profile"]["wake_phrase"] == "ei assistente"


def test_vocabulary_not_checked_without_local_model(isolated_profile, monkeypatch):
    monkeypatch.setattr(wake_word, "_get_model", lambda download=False: None)
    status, data = _post({"name": "Nova", "style": "", "wake_phrase": ""})
    assert status == 200
    assert data["wake_phrase_check"]["checked"] is False


def test_detector_follows_profile_phrase(isolated_profile, vocabulary, monkeypatch):
    detector = wake_word.WakeWordDetector()
    assert detector.wake_words == {"ei assistente"}
    assert detector._matches_wake_word("ei assistente abra o navegador")

    fake_server = ModuleType("app.ui.panel.server")
    fake_server._wake_word_detector = detector
    monkeypatch.setitem(sys.modules, "app.ui.panel.server", fake_server)
    status, _ = _post({"name": "Nova", "style": "", "wake_phrase": ""})
    assert status == 200
    assert detector.wake_words == {"ei nova"}
    assert not detector._matches_wake_word("ei assistente")
