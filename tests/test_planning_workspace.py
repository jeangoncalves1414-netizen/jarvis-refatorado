from __future__ import annotations

from app.agent.tools import planning_workspace as planning_tool_module
from app.agent.tools.planning_workspace import PlanningWorkspaceTool
from app.services.planning_workspace import PlanningWorkspaceService
from app.storage import memory_store
from app.ui.panel.api import planning as planning_api


class _MemoryStoreSpy:
    values: list[tuple[str, str]] = []

    def add_preference(self, key: str, value: str) -> None:
        self.values.append((key, value))


def test_workspace_persists_content_and_explicit_auto_open_consent(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_store, "MemoryStore", _MemoryStoreSpy)
    service = PlanningWorkspaceService(tmp_path / "planning.json")

    opened = service.open("chat-1", "Plano de Sucesso")
    assert opened["workspace"]["is_open"] is True
    assert opened["workspace"]["title"] == "Plano de Sucesso"

    service.append("chat-1", "Definir a primeira meta de 90 dias.")
    saved = service.update("chat-1", content="# Plano\n\n## Próximos passos\nComeçar hoje.")
    assert "Começar hoje" in saved["workspace"]["content"]

    service.set_auto_open(True)
    assert service.get("chat-1")["preferences"]["auto_open_for_planning"] is True
    assert _MemoryStoreSpy.values[-1][0] == "planning_workspace_auto_open"


def test_tool_and_api_share_the_same_workspace_contract(tmp_path, monkeypatch):
    service = PlanningWorkspaceService(tmp_path / "planning.json")
    monkeypatch.setattr(planning_tool_module, "planning_workspace", service)
    monkeypatch.setattr(planning_api, "planning_workspace", service)

    tool = PlanningWorkspaceTool()
    opened = tool.execute({"action": "open", "title": "Plano de Estudos"}, {"session_id": "chat-2"})
    assert opened.ok is True
    assert opened.data["workspace"]["is_open"] is True

    status, payload = planning_api.handle_planning_post(
        "/api/planning",
        b'{"session_id":"chat-2","action":"append","content":"Revisar matematica."}',
        object(),
    )
    assert status == 200
    assert "Revisar matematica" in payload["workspace"]["content"]
