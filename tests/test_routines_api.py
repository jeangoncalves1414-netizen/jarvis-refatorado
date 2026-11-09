from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.routines import service as service_module
from app.routines.runner import RoutineRunner
from app.ui.panel.api.routines import handle_routines_get, handle_routines_post


@pytest.fixture
def api(monkeypatch, isolated_lote6_data):
    runner = RoutineRunner(spawn=lambda fn: None)
    monkeypatch.setattr(service_module.routine_service, "runner", runner)
    return isolated_lote6_data


def get(path):
    parts = [part for part in path.split("?")[0].split("/") if part]
    return handle_routines_get(parts, SimpleNamespace(path=path))


def post(path, payload):
    body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    return handle_routines_post(path, body, None)


ROUTINE = {
    "name": "Bom dia",
    "steps": [
        {"tool": "spotify", "operation": "open"},
        {"tool": "web_search", "operation": "open_url", "params": {"query": "https://youtube.com"}, "delay_before": 10},
    ],
    "triggers": [{"type": "daily", "time": "08:00"}, {"type": "command", "slash": "bom-dia"}],
}


def test_create_list_edit_enable_run_and_delete(api):
    status, created = post("/api/routines", ROUTINE)
    assert status == 200 and created["ok"] and created["next_run"]
    routine_id = created["routine"]["id"]

    status, listed = get("/api/routines")
    assert status == 200 and listed["routines"][0]["next_run_label"]
    assert listed["commands"] == [{"routine_id": routine_id, "name": "Bom dia", "slash": "bom-dia"}]

    reordered = {"steps": list(reversed(ROUTINE["steps"]))}
    status, updated = post(f"/api/routines/{routine_id}", reordered)
    assert status == 200 and [step["tool"] for step in updated["routine"]["steps"]] == ["web_search", "spotify"]
    assert updated["routine"]["name"] == "Bom dia"

    status, disabled = post(f"/api/routines/{routine_id}/enable", {"enabled": False})
    assert status == 200 and disabled["routine"]["enabled"] is False and disabled["routine"]["next_run"] is None
    assert post(f"/api/routines/{routine_id}/enable", {"enabled": "sim"})[0] == 400

    status, started = post(f"/api/routines/{routine_id}/run", {})
    assert status == 200
    run = api.store.run_details(started["run_id"])["run"]
    assert run["origin"] == "routine"
    assert post(f"/api/routines/{routine_id}/run", {})[0] == 409

    status, detail = get(f"/api/routines/{routine_id}")
    assert status == 200 and detail["history"][0]["run_id"] == started["run_id"]

    assert post(f"/api/routines/{routine_id}/delete", {}) == (200, {"ok": True})
    assert get(f"/api/routines/{routine_id}")[0] == 404


def test_meta_lists_operations_with_risk(api):
    status, meta = get("/api/routines/meta")
    assert status == 200
    tools = {item["tool"]: item for item in meta["tools"]}
    assert "routine" not in tools and "wait" not in tools
    risks = {op["name"]: op["risk"] for op in tools["task_tool"]["operations"]}
    assert risks["delete"] == "high" and risks["list"] == "observe"
    assert tools["spotify"]["operation_argument"] == "action" and "query" in tools["spotify"]["params"]


def test_next_and_alerts_and_errors(api):
    post("/api/routines", ROUTINE)
    status, upcoming = get("/api/routines/next?limit=3")
    assert status == 200 and len(upcoming["next_runs"]) == 3 and upcoming["next_runs"][0]["name"] == "Bom dia"
    assert get("/api/routines/next?limit=0")[0] == 400
    assert get("/api/routines/alerts")[1]["alerts"] == []
    assert post("/api/routines", b"{nao json")[0] == 400
    status, error = post("/api/routines", {**ROUTINE, "steps": [{"tool": "nao_existe"}]})
    assert status == 400 and "ferramenta desconhecida" in error["error"]
    status, error = post("/api/routines", ROUTINE)
    assert status == 400 and "já usa o comando /bom-dia" in error["error"]
    assert post("/api/routines/rt_nao", {"name": "x"})[0] == 404
    assert post("/api/routines/rt_nao/run", {})[0] == 404
    assert get("/api/outra") is None
