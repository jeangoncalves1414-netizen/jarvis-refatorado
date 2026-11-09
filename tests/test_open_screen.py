"""Ferramenta open_screen: o agente só escolhe telas que existem no app (lote 6, fase 1)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.open_screen import SCREENS, OpenScreenTool, resolve_screen
from app.agent.tools.registry import GENERAL_TOOL_NAMES, ToolRegistry

NAVIGATION = Path(__file__).resolve().parents[1] / "frontend" / "src" / "navigation.ts"


def test_screen_ids_mirror_frontend_navigation():
    ids = re.findall(r"\{\s*id:\s*'([^']+)'", NAVIGATION.read_text(encoding="utf-8"))
    assert ids and list(SCREENS) == ids
    assert OpenScreenTool().parameters["properties"]["screen"]["enum"] == ids


@pytest.mark.parametrize(("value", "screen"), [
    ("Painel pessoal", "Painel pessoal"), ("painel", "Painel pessoal"), ("Evolucao", "Evolução"),
    ("life os", "Evolução"), ("agenda", "Calendário"), ("CONFIGURAÇÕES", "Configurações"),
])
def test_aliases_resolve_to_known_screens(value, screen):
    assert resolve_screen(value) == screen


def test_invalid_screen_is_refused():
    result = OpenScreenTool().execute({"screen": "Painel secreto"})
    assert not result.ok and "Tela desconhecida" in result.message
    assert not OpenScreenTool().execute({"screen": ["Chat"]}).ok


def test_result_carries_ui_screen_and_risk_is_observe():
    result = OpenScreenTool().execute({"screen": "Painel pessoal"})
    assert result.ok and result.data["ui_screen"] == {"screen": "Painel pessoal"}
    marker = OpenScreenTool().execute({"command": "painel"})
    assert marker.ok and marker.data["ui_screen"] == {"screen": "Painel pessoal"}
    assert TOOL_CATALOG["open_screen"].risk_for({"screen": "Chat"}) == "observe"
    registry = ToolRegistry()
    assert "open_screen" in GENERAL_TOOL_NAMES and registry.get_tool("open_screen") is not None
    assert registry.get_tool_metadata("open_screen") is TOOL_CATALOG["open_screen"]


def test_groq_receives_personal_tools_by_keyword():
    registry = ToolRegistry()
    allowed = registry.allowed_tool_names(mode="general", provider="groq", user_text="Abre o painel e adiciona os hábitos; bebi 3L de água")
    assert {"open_screen", "habit_tool", "lifeos_tool"} <= allowed
    assert "habit_tool" not in registry.allowed_tool_names(mode="general", provider="groq", user_text="oi")
    assert "notes" not in registry.allowed_tool_names(mode="general", provider="groq", user_text="oi")
