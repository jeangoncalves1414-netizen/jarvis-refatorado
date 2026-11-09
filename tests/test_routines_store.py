from __future__ import annotations

import pytest

from app.agent.tools.registry import ToolRegistry
from app.routines.models import RoutineError, step_arguments, validate_routine
from app.storage.routine_store import MAX_HISTORY, RoutineStore


@pytest.fixture(scope="module")
def registry():
    return ToolRegistry()


def _payload(**overrides):
    payload = {
        "name": "Bom dia",
        "steps": [
            {"tool": "open_windows_app", "operation": "open", "params": {"app_name": "chrome"}},
            {"tool": "spotify", "operation": "search_play", "params": {"query": "Foco"}, "delay_before": 30},
        ],
        "triggers": [{"type": "daily", "time": "8:00"}],
    }
    payload.update(overrides)
    return payload


def test_validate_cleans_fields_and_builds_arguments(registry):
    fields = validate_routine(_payload(), registry)
    assert fields["triggers"] == [{"type": "daily", "time": "08:00"}]
    assert fields["catch_up_minutes"] == 15 and fields["enabled"] is True and fields["quiet"] is None
    first, second = fields["steps"]
    assert (first["id"], first["label"], first["on_failure"], first["timeout"]) == ("s1", "Abrir chrome", "stop", None)
    assert second["delay_before"] == 30 and second["label"] == "Tocar Foco no Spotify"
    assert step_arguments(second, "action") == {"query": "Foco", "action": "search_play"}


def test_retry_text_form_is_accepted(registry):
    fields = validate_routine(_payload(steps=[{"tool": "spotify", "operation": "open", "on_failure": "retry(2)"}]), registry)
    assert (fields["steps"][0]["on_failure"], fields["steps"][0]["retries"]) == ("retry", 2)


@pytest.mark.parametrize(("overrides", "message"), [
    ({"steps": [{"tool": "nao_existe", "operation": "x"}]}, "ferramenta desconhecida"),
    ({"steps": [{"tool": "routine", "operation": "list"}]}, "não pode ser etapa"),
    ({"steps": [{"tool": "wait", "params": {"seconds": 5}}]}, "Esperar antes"),
    ({"steps": [{"tool": "spotify", "operation": "explodir"}]}, "operação 'explodir'"),
    ({"steps": [{"tool": "spotify", "operation": "open", "delay_before": 4000}]}, "entre 0 e 3600"),
    ({"steps": [{"tool": "spotify", "operation": "open", "params": {"inventado": 1}}]}, "não existe nesta ferramenta"),
    ({"steps": [{"tool": "spotify", "operation": "open"}] * 21}, "no máximo 20 etapas"),
    ({"steps": []}, "pelo menos uma etapa"),
    ({"name": "  "}, "nome"),
    ({"triggers": [{"type": "daily", "time": "08:00"}, {"type": "interval", "minutes": 30}]}, "1 gatilho de horário"),
    ({"triggers": [{"type": "command", "slash": "Foco Já"}]}, "2 a 30 letras"),
    ({"triggers": [{"type": "command", "slash": "foco"}]}, "já existe no app"),
    ({"triggers": [{"type": "interval", "minutes": 2}]}, "entre 5 e 1440"),
    ({"triggers": [{"type": "weekly", "days": ["xyz"], "time": "08:00"}]}, "dia inválido"),
    ({"triggers": [{"type": "daily", "time": "25:00"}]}, "HH:MM"),
    ({"quiet": {"start": "22:00", "end": "22:00"}}, "diferentes"),
])
def test_validation_rejects_with_portuguese_message(registry, overrides, message):
    with pytest.raises(RoutineError) as error:
        validate_routine(_payload(**overrides), registry)
    assert message in str(error.value)


def test_crud_and_persistence(tmp_path, registry):
    path = tmp_path / "routines.sqlite3"
    store = RoutineStore(path)
    created = store.create(validate_routine(_payload(), registry))
    assert created["id"].startswith("rt_") and created["enabled"] is True and len(created["steps"]) == 2
    store.update(created["id"], {"name": "Manhã", "quiet": {"start": "22:00", "end": "07:00"}})
    store.set_enabled(created["id"], False)
    store.set_last(created["id"], last_status="succeeded", last_run_id="run_x")
    reopened = RoutineStore(path).get(created["id"])
    assert reopened["name"] == "Manhã" and reopened["enabled"] is False
    assert reopened["quiet"] == {"start": "22:00", "end": "07:00"} and reopened["last_status"] == "succeeded"
    assert [item["id"] for item in RoutineStore(path).list()] == [created["id"]]
    store.add_run(created["id"], "manual", status="succeeded")
    assert store.delete(created["id"]) is True
    assert store.get(created["id"]) is None and store.history(created["id"]) == []
    with pytest.raises(KeyError):
        store.update(created["id"], {"name": "x"})


def test_history_is_pruned_and_interrupted_on_restart(tmp_path, registry):
    store = RoutineStore(tmp_path / "routines.sqlite3")
    routine = store.create(validate_routine(_payload(), registry))
    for _ in range(MAX_HISTORY + 5):
        store.add_run(routine["id"], "schedule", status="succeeded")
    assert len(store.history(routine["id"], limit=500)) == MAX_HISTORY
    running = store.add_run(routine["id"], "manual")
    paused = store.add_run(routine["id"], "manual", status="paused")
    store.set_last(routine["id"], last_status="paused")
    assert store.mark_interrupted() == 2
    assert store.get_run(running["id"])["status"] == "interrupted"
    assert store.get_run(paused["id"])["status"] == "interrupted"
    assert store.get(routine["id"])["last_status"] == "interrupted"
    store.add_run(routine["id"], "event", status="alert", summary="CPU alta")
    assert [item["summary"] for item in store.alerts()] == ["CPU alta"]
