import os
import json
import pytest
from app.services.lifeos import LifeOSService
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.lifeos_tool import LifeOSTool
from app.services.proactive import ProactiveService

def test_lifeos_summary():
    summary = LifeOSService.get_daily_summary()
    assert summary.get("ok") is True
    assert "habits" in summary
    assert "water" in summary
    assert "workout" in summary
    assert "study" in summary
    assert "motivational" in summary
    
    # Verify motivational speech format
    motiv = summary["motivational"]
    assert "speech" in motiv
    assert "quote" in motiv
    assert "author" in motiv
    assert len(motiv["speech"]) > 10

def test_lifeos_water_and_habit():
    # Test adding water
    water_res = LifeOSService.add_water(250)
    assert water_res.get("ok") is True
    assert water_res.get("added_ml") == 250
    assert water_res.get("total_ml") >= 250

    # Test toggling habit
    habit_res = LifeOSService.toggle_habit("agua", completed=True)
    assert habit_res.get("ok") is True
    assert "title" in habit_res

def test_lifeos_tool_in_registry():
    registry = ToolRegistry()
    tool = registry.get_tool("lifeos_tool")
    assert tool is not None
    assert tool.name == "lifeos_tool"

    # Test summary action
    res = registry.execute_tool("lifeos_tool", {"action": "summary"})
    assert res.ok is True
    assert "Life OS" in res.message

    # Test list_habits action
    res_habits = registry.execute_tool("lifeos_tool", {"action": "list_habits"})
    assert res_habits.ok is True
    assert "Hábitos no Life OS" in res_habits.message

def test_proactive_briefing_with_lifeos():
    proactive = ProactiveService()
    briefing = proactive.generate_briefing_text()
    assert briefing is not None
    assert len(briefing) > 20
    # Deve conter a seção de evolução ou fala motivacional
    assert "Evolução Pessoal & Life OS" in briefing or "Bom dia" in briefing
    print("\n[BRIEFING PREVIEW]:\n", briefing)

if __name__ == "__main__":
    pytest.main(["-v", __file__])
