from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

import pytest

from app.agent.tools.registry import ToolRegistry
from app.routines import triggers as trig
from app.routines.service import RoutineService
from app.storage import routine_store as routine_store_module

TZ = trig.TZ
FRIDAY_9 = datetime(2026, 11, 13, 9, 0, tzinfo=TZ)


def _routine(trigger, **extra):
    return {"id": "rt_x", "name": "R", "enabled": True, "steps": [], "triggers": [trigger],
            "created_at": datetime(2026, 11, 1, tzinfo=TZ).timestamp(), "updated_at": datetime(2026, 11, 1, tzinfo=TZ).timestamp(), **extra}


def test_next_runs_for_each_time_trigger():
    daily = trig.next_runs(_routine({"type": "daily", "time": "08:00"}), FRIDAY_9, 2)
    assert [item.isoformat() for item in daily] == ["2026-11-14T08:00:00-03:00", "2026-11-15T08:00:00-03:00"]
    weekdays = trig.next_run(_routine({"type": "weekdays", "time": "08:00"}), FRIDAY_9)
    assert weekdays.isoformat() == "2026-11-16T08:00:00-03:00"
    weekly = trig.next_runs(_routine({"type": "weekly", "days": ["mon", "wed"], "time": "07:30"}), FRIDAY_9, 2)
    assert [(item.weekday(), item.strftime("%H:%M")) for item in weekly] == [(0, "07:30"), (2, "07:30")]
    interval = trig.next_runs(_routine({"type": "interval", "minutes": 30}), FRIDAY_9, 2)
    assert [item.strftime("%H:%M") for item in interval] == ["09:30", "10:00"]
    assert trig.next_run(_routine({"type": "at", "datetime": "2026-11-13T08:00"}), FRIDAY_9) is None
    assert trig.next_run(_routine({"type": "at", "datetime": "2026-11-20T08:00"}), FRIDAY_9).isoformat() == "2026-11-20T08:00:00-03:00"
    assert trig.next_run(_routine({"type": "daily", "time": "08:00"}, enabled=False), FRIDAY_9) is None
    assert trig.next_run(_routine({"type": "voice", "phrase": "modo foco"}), FRIDAY_9) is None


def test_quiet_hours_cross_midnight():
    quiet = {"start": "22:00", "end": "07:00"}
    assert trig.in_quiet_hours(quiet, datetime(2026, 11, 13, 23, 30, tzinfo=TZ))
    assert trig.in_quiet_hours(quiet, datetime(2026, 11, 13, 6, 59, tzinfo=TZ))
    assert not trig.in_quiet_hours(quiet, datetime(2026, 11, 13, 7, 0, tzinfo=TZ))
    assert not trig.in_quiet_hours(None, FRIDAY_9)
    assert trig.in_quiet_hours({"start": "12:00", "end": "13:00"}, datetime(2026, 11, 13, 12, 30, tzinfo=TZ))


def test_missed_fires_with_pc_off_for_three_days():
    routine = _routine({"type": "daily", "time": "08:00"})
    since = datetime(2026, 11, 10, 9, 0, tzinfo=TZ)
    missed = trig.missed_fires(routine, since, since + timedelta(days=3))
    assert [item.day for item in missed] == [11, 12, 13]


def test_descriptions_in_portuguese():
    assert trig.describe_trigger({"type": "daily", "time": "08:00"}) == "Todo dia às 08:00"
    assert trig.describe_trigger({"type": "weekdays", "time": "08:00"}) == "Dias úteis às 08:00"
    assert trig.describe_trigger({"type": "weekly", "days": ["mon", "wed"], "time": "08:00"}) == "Seg e qua às 08:00"
    assert trig.describe_trigger({"type": "interval", "minutes": 30}) == "A cada 30 min"
    assert trig.describe_trigger({"type": "at", "datetime": "2026-11-10T08:00"}) == "Em 10/11 às 08:00"
    assert trig.describe_trigger({"type": "voice", "phrase": "modo foco"}) == "Voz: modo foco"
    assert trig.describe_when(datetime(2026, 11, 14, 8, 0, tzinfo=TZ), FRIDAY_9) == "amanhã 08:00"
    assert trig.describe_when(datetime(2026, 11, 13, 18, 0, tzinfo=TZ), FRIDAY_9) == "hoje 18:00"


# ── serviço e agendador ────────────────────────────────────────────────────────

class StubRunner:
    def __init__(self):
        self.registry = None
        self.started = []

    def is_running(self, _routine_id):
        return False

    def active(self):
        return []

    def start(self, routine, trigger_kind, scheduled_for=None):
        self.started.append((routine["id"], trigger_kind, scheduled_for))
        return f"run_{len(self.started)}"


@pytest.fixture
def service():
    svc = RoutineService(runner=StubRunner(), registry=ToolRegistry())
    yield svc
    svc.stop()


def _create(svc, **overrides):
    payload = {"name": "Bom dia", "steps": [{"tool": "spotify", "operation": "open"}], "triggers": [{"type": "daily", "time": "08:00"}]}
    payload.update(overrides)
    return svc.create(payload)["routine"]


def _backdate(routine_id, when):
    store = routine_store_module.routine_store
    with sqlite3.connect(store.path) as db:
        db.execute("UPDATE routines SET created_at = ?, updated_at = ? WHERE id = ?", (when.timestamp(), when.timestamp(), routine_id))


def test_sync_jobs_follows_enable_disable_and_delete(service):
    service.start(paused=True)
    routine = _create(service)
    voice_only = _create(service, name="Voz", triggers=[{"type": "voice", "phrase": "modo foco"}])
    jobs = lambda: sorted(job.id for job in service.scheduler.get_jobs() if job.id.startswith("rt_"))
    assert jobs() == [routine["id"]]
    assert voice_only["next_run"] is None
    service.set_enabled(routine["id"], False)
    assert jobs() == []
    service.set_enabled(routine["id"], True)
    assert jobs() == [routine["id"]]
    service.delete(routine["id"])
    assert jobs() == []
    assert any(job.id == "routines:sweep" for job in service.scheduler.get_jobs())


def test_recovery_runs_last_fire_within_tolerance_and_marks_older_as_missed(service):
    routine = _create(service)
    _backdate(routine["id"], datetime(2026, 11, 9, 7, 0, tzinfo=TZ))
    started = service.recover(datetime(2026, 11, 10, 8, 10, tzinfo=TZ))
    assert started == ["run_1"]
    assert service.runner.started[0][:2] == (routine["id"], "catch_up")
    history = routine_store_module.routine_store.history(routine["id"])
    assert [item["status"] for item in history] == ["missed"]
    assert "09/11 08:00" in history[0]["summary"]


def test_recovery_beyond_tolerance_only_records_missed(service):
    routine = _create(service)
    _backdate(routine["id"], datetime(2026, 11, 7, 7, 0, tzinfo=TZ))
    assert service.recover(datetime(2026, 11, 10, 10, 0, tzinfo=TZ)) == []
    assert service.runner.started == []
    history = routine_store_module.routine_store.history(routine["id"])
    assert [item["status"] for item in history] == ["missed"]
    assert history[0]["summary"].startswith("4 execuções perdidas")
    stored = routine_store_module.routine_store.get(routine["id"])
    assert stored["last_status"] == "missed"
    # Já registrado: a próxima recuperação não conta de novo.
    assert service.recover(datetime(2026, 11, 10, 10, 5, tzinfo=TZ)) == []
    assert len(routine_store_module.routine_store.history(routine["id"])) == 1


def test_fire_inside_quiet_hours_is_skipped(service, monkeypatch):
    routine = _create(service, quiet={"start": "22:00", "end": "07:00"})
    monkeypatch.setattr(service, "_now", lambda: datetime(2026, 11, 10, 23, 0, tzinfo=TZ))
    assert service._fire(routine["id"]) is None
    assert service.runner.started == []
    assert routine_store_module.routine_store.history(routine["id"])[0]["summary"] == "Pulada: horário de silêncio."
    monkeypatch.setattr(service, "_now", lambda: datetime(2026, 11, 10, 8, 0, tzinfo=TZ))
    assert service._fire(routine["id"]) == "run_1"


def test_match_phrase_and_unique_triggers(service):
    routine = _create(service, name="Foco", triggers=[{"type": "voice", "phrase": "Modo Foco"}, {"type": "command", "slash": "foco-ja"}])
    assert service.match_phrase("Jarvis, modo foco!")["id"] == routine["id"]
    assert service.match_phrase("modo foco") is not None
    assert service.match_phrase("me explica o modo foco") is None
    assert service.command_triggers() == [{"routine_id": routine["id"], "name": "Foco", "slash": "foco-ja"}]
    from app.routines.models import RoutineError
    with pytest.raises(RoutineError, match="já usa"):
        _create(service, name="Outra", triggers=[{"type": "voice", "phrase": "modo foco"}])
