"""Testes para o Sistema de Personas Modular (app.agent.personas, persona_tool, api)."""
import json
import os
import pytest

from app.agent.personas import (
    DEFAULT_PERSONA,
    VALID_TONES,
    get_persona,
    update_persona,
    reset_persona,
    get_persona_context,
)
from app.agent.tools.persona_tool import PersonaTool
from app.ui.panel.api.persona import handle_persona_get, handle_persona_post


@pytest.fixture(autouse=True)
def isolated_persona_dir(tmp_path, monkeypatch):
    """Garante que cada teste rode em um diretório temporário isolado."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("JARVIS_DATA_DIR", str(data_dir))
    reset_persona()
    yield data_dir


def test_persona_defaults():
    p = get_persona()
    assert p["name"] == "Jarvis"
    assert p["tone"] == "amigável"
    assert p["morning_challenge"]["enabled"] is True
    assert "polichinelos" in p["morning_challenge"]["text"]
    assert p["custom_rules"] == ""


def test_persona_update_name_and_tone():
    updated = update_persona({"name": "Sexta-Feira", "tone": "militar"})
    assert updated["name"] == "Sexta-Feira"
    assert updated["tone"] == "militar"

    persisted = get_persona()
    assert persisted["name"] == "Sexta-Feira"
    assert persisted["tone"] == "militar"


def test_persona_update_challenge():
    update_persona({
        "morning_challenge": {
            "enabled": False,
            "text": "20 agachamentos",
        }
    })
    p = get_persona()
    assert p["morning_challenge"]["enabled"] is False
    assert p["morning_challenge"]["text"] == "20 agachamentos"

    # Atualização via campos planos
    update_persona({
        "morning_challenge_enabled": True,
        "morning_challenge_text": "30 abdominais",
    })
    p2 = get_persona()
    assert p2["morning_challenge"]["enabled"] is True
    assert p2["morning_challenge"]["text"] == "30 abdominais"


def test_persona_tone_synonyms():
    p1 = update_persona({"tone": "sarcastico leve"})
    assert p1["tone"] == "sarcástico leve"

    p2 = update_persona({"tone": "engracado"})
    assert p2["tone"] == "bem-humorado"

    p3 = update_persona({"tone": "profissional"})
    assert p3["tone"] == "formal"


def test_persona_custom_rules_and_context():
    update_persona({
        "name": "Friday",
        "tone": "sarcástico leve",
        "custom_rules": "Nunca use chavões. Seja conciso e elegante.",
    })
    ctx = get_persona_context()
    assert "Friday" in ctx
    assert "sarcástico leve" in ctx
    assert "Nunca use chavões" in ctx
    assert "Desafio matinal ativo" in ctx


def test_persona_reset():
    update_persona({"name": "Custom", "tone": "militar"})
    assert get_persona()["name"] == "Custom"
    reset_persona()
    p = get_persona()
    assert p["name"] == "Jarvis"
    assert p["tone"] == "amigável"


def test_persona_tool_run():
    tool = PersonaTool()
    assert tool.name == "persona_tool"

    # Action: get
    res_get = tool.run({"action": "get"})
    assert res_get.ok
    assert "Jarvis" in res_get.message

    # Action: set_name
    res_name = tool.run({"action": "set_name", "name": "Ultron"})
    assert res_name.ok
    assert get_persona()["name"] == "Ultron"

    # Action: set_tone
    res_tone = tool.run({"action": "set_tone", "tone": "formal"})
    assert res_tone.ok
    assert get_persona()["tone"] == "formal"

    # Action: set_challenge
    res_ch = tool.run({
        "action": "set_challenge",
        "morning_challenge_enabled": False,
        "morning_challenge_text": "Caminhada de 20 min",
    })
    assert res_ch.ok
    p = get_persona()
    assert p["morning_challenge"]["enabled"] is False
    assert p["morning_challenge"]["text"] == "Caminhada de 20 min"

    # Action: reset
    res_reset = tool.run({"action": "reset"})
    assert res_reset.ok
    assert get_persona()["name"] == "Jarvis"


def test_persona_api_get():
    class DummyHandler:
        path = "/api/persona"

    result = handle_persona_get(["api", "persona"], DummyHandler())
    assert result is not None
    code, data = result
    assert code == 200
    assert data["ok"] is True
    assert data["persona"]["name"] == "Jarvis"


def test_persona_api_post():
    class DummyHandler:
        path = "/api/persona"

    payload = json.dumps({"name": "Vision", "tone": "formal"}).encode("utf-8")
    result = handle_persona_post("/api/persona", payload, DummyHandler())
    assert result is not None
    code, data = result
    assert code == 200
    assert data["ok"] is True
    assert data["persona"]["name"] == "Vision"
    assert data["persona"]["tone"] == "formal"


def test_persona_api_preview_endpoints():
    class DummyHandler:
        path = "/api/persona/preview-morning"

    res_morning = handle_persona_get(["api", "persona", "preview-morning"], DummyHandler())
    assert res_morning is not None
    assert res_morning[0] == 200
    assert "text" in res_morning[1]
    assert len(res_morning[1]["text"]) > 10

    res_evening = handle_persona_get(["api", "persona", "preview-evening"], DummyHandler())
    assert res_evening is not None
    assert res_evening[0] == 200
    assert "text" in res_evening[1]
    assert len(res_evening[1]["text"]) > 10
