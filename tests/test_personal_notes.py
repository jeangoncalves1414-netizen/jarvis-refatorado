from types import SimpleNamespace
from urllib.parse import urlencode

import pytest

from app.agent.popups import popups_for_result
from app.ui.panel.api.recent_notes import handle_recent_notes_get


def get_notes(route, **query):
    url = "/api/notes/" + route + "?" + urlencode(query)
    return handle_recent_notes_get(["api", "notes", route], SimpleNamespace(path=url))


def test_saved_and_daily_notes_can_be_reopened(isolated_lote6_data):
    from app.agent.tools.memory_vault_tool import VaultDailyNoteTool, VaultSaveNoteTool
    tools = [
        (VaultSaveNoteTool(), {"title": "Ideia de teste", "content": "Texto do teste"}),
        (VaultDailyNoteTool(), {"entry": "Entrada de teste"}),
    ]
    expected = []
    for tool, args in tools:
        result = tool.execute(args)
        assert result.ok
        template, params, meta = popups_for_result(tool.name, args, result)[0]
        assert template == "info" and params["tone"] == "ok"
        path = meta["saved_note_path"]
        expected.append(path)
        status, detail = get_notes("read", path=path)
        assert status == 200
        assert (args.get("entry") or args["content"]) in detail["content"]
    status, data = get_notes("recent")
    assert status == 200
    assert {row["path"] for row in data["notes"]} == set(expected)
    assert all(row["modified"] > 0 and row["title"] for row in data["notes"])


@pytest.mark.parametrize("path,status", [
    ("02-User-Profile/USER-PROFILE.md", 400),
    ("05-Notas/../arquivo.md", 400),
    ("05-Notas/sumiu.md", 404),
])
def test_note_reader_only_opens_personal_markdown(isolated_lote6_data, path, status):
    got, data = get_notes("read", path=path)
    assert got == status and data["ok"] is False
