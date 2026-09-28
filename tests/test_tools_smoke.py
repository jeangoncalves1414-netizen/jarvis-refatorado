from __future__ import annotations

import pytest
from app.agent.tools.registry import ToolRegistry, GENERAL_TOOL_NAMES, TUTOR_TOOL_NAMES
from app.agent.tools.file_manager import FileManagerTool
from app.agent.tools.system_control import SystemControlTool
from app.agent.tools.web_search import WebSearchTool
from app.agent.tools.realtime_tool import RealTimeTool
from app.agent.tools.lifestyle_tools import HabitTool, TaskTool, FinanceTool


def test_tool_registry_smoke(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    assert len(registry.tools) > 10, "Deveria haver pelo menos 10 ferramentas registradas"

    for name, tool in registry.tools.items():
        assert tool.name, f"Ferramenta {name} sem nome"
        assert tool.description, f"Ferramenta {name} sem descrição"
        assert callable(tool.run), f"Ferramenta {name} sem método run"


def test_file_manager_tool_smoke(tmp_path):
    tool = FileManagerTool(base_folder=str(tmp_path))
    assert tool.name == "file_manager"

    # Test list directory
    res_list = tool.execute({"action": "list", "path": ""})
    assert res_list.ok is True

    # Test read file
    test_file = tmp_path / "smoke_test.txt"
    test_file.write_text("Smoke test Jarvis content", encoding="utf-8")
    res_read = tool.execute({"action": "read", "path": "smoke_test.txt"})
    assert res_read.ok is True
    assert "Smoke test Jarvis content" in str(res_read.data.get("content"))


def test_system_control_tool_smoke():
    tool = SystemControlTool()
    assert tool.name == "system_control"

    # Volume mute/unmute action
    res = tool.execute({"action": "volume_mute"})
    assert res.ok is True


def test_web_search_tool_smoke():
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert tool.description


def test_realtime_tool_smoke(monkeypatch):
    tool = RealTimeTool()
    assert tool.name == "realtime"

    from app.services.realtime import RealTimeService
    monkeypatch.setattr(RealTimeService, "get_holidays", lambda year: {"ok": True, "year": 2026, "total": 1, "holidays": [{"name": "Ano Novo", "date": "2026-01-01"}]})
    res = tool.execute({"action": "get_holidays", "year": 2026})
    assert res.ok is True


def test_lifestyle_tools_smoke(tmp_path):
    habit = HabitTool()
    task = TaskTool()
    finance = FinanceTool()

    assert habit.name == "habit_tool"
    assert task.name == "task_tool"
    assert finance.name == "finance_tool"
