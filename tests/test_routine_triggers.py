"""Testes dos gatilhos de eventos e do observador em segundo plano (Fase 3)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from zoneinfo import ZoneInfo

import pytest

from app.routines import triggers as trig
from app.routines.models import RoutineError, validate_routine
from app.routines.watcher import EventWatcher
from app.storage import runtime_settings
from app.ui.panel.api import settings as settings_api

TZ = ZoneInfo("America/Sao_Paulo")


@dataclass
class DummyCalendarEvent:
    id: str
    title: str
    start: datetime


class FakeHandler:
    def __init__(self, path: str = ""):
        self.path = path


@pytest.fixture
def isolated_event_settings(tmp_path, monkeypatch):
    settings_file = tmp_path / "runtime_settings.json"
    monkeypatch.setattr("app.storage.runtime_settings.RUNTIME_SETTINGS_FILE", str(settings_file))
    return settings_file


def test_event_settings_defaults_and_crud(isolated_event_settings):
    # Valores padrão
    current = runtime_settings.get_event_settings()
    assert current["enabled"] is True
    assert current["interval_seconds"] == 15
    assert current["cooldown_minutes"] == 30
    assert current["cpu"]["enabled"] is False
    assert current["cpu"]["threshold"] == 90
    assert current["cpu"]["for_seconds"] == 120

    # Atualização válida
    saved = runtime_settings.set_event_settings({
        "enabled": True,
        "interval_seconds": 20,
        "cooldown_minutes": 45,
        "disk_path": "D:\\",
        "cpu": {"enabled": True, "threshold": 85, "for_seconds": 60},
    })
    assert saved["interval_seconds"] == 20
    assert saved["cooldown_minutes"] == 45
    assert saved["disk_path"] == "D:\\"
    assert saved["cpu"]["enabled"] is True
    assert saved["cpu"]["threshold"] == 85
    assert saved["cpu"]["for_seconds"] == 60

    # Releitura confirma persistência no JSON
    reloaded = runtime_settings.get_event_settings()
    assert reloaded["interval_seconds"] == 20
    assert reloaded["cpu"]["threshold"] == 85


def test_event_settings_validation_errors(isolated_event_settings):
    # Desconhecido
    with pytest.raises(ValueError, match="Campo desconhecido"):
        runtime_settings.set_event_settings({"inexistente": 123})

    # interval_seconds fora da faixa
    with pytest.raises(ValueError, match="intervalo de verificação"):
        runtime_settings.set_event_settings({"interval_seconds": 5})
    with pytest.raises(ValueError, match="intervalo de verificação"):
        runtime_settings.set_event_settings({"interval_seconds": 200})

    # cooldown fora da faixa
    with pytest.raises(ValueError, match="intervalo entre alertas"):
        runtime_settings.set_event_settings({"cooldown_minutes": 0})

    # threshold fora da faixa
    with pytest.raises(ValueError, match="limiar de CPU"):
        runtime_settings.set_event_settings({"cpu": {"threshold": 40}})
    with pytest.raises(ValueError, match="limiar de CPU"):
        runtime_settings.set_event_settings({"cpu": {"threshold": 100}})

    # for_seconds fora da faixa
    with pytest.raises(ValueError, match="duração de RAM"):
        runtime_settings.set_event_settings({"ram": {"for_seconds": 5000}})


def test_settings_api_events_routes(isolated_event_settings):
    # GET
    code, data = settings_api.handle_settings_get(["api", "settings", "events"], FakeHandler("/api/settings/events"))
    assert code == 200
    assert data["ok"] is True
    assert "settings" in data

    # POST sucesso
    body = json.dumps({"settings": {"interval_seconds": 30, "ram": {"enabled": True, "threshold": 88, "for_seconds": 90}}}).encode("utf-8")
    code, data = settings_api.handle_settings_post("/api/settings/events", body, FakeHandler())
    assert code == 200
    assert data["ok"] is True
    assert data["settings"]["interval_seconds"] == 30
    assert data["settings"]["ram"]["threshold"] == 88

    # POST inválido -> 400
    bad_body = json.dumps({"settings": {"interval_seconds": 999}}).encode("utf-8")
    code, data = settings_api.handle_settings_post("/api/settings/events", bad_body, FakeHandler())
    assert code == 400
    assert data["ok"] is False
    assert "intervalo de verificação" in data["error"]


def test_event_trigger_model_validation():
    # Gatilho de evento válido
    payload = {
        "name": "Alerta CPU Alta",
        "enabled": True,
        "triggers": [{
            "type": "event",
            "event": "resource",
            "params": {"metric": "cpu", "threshold": 92, "for_seconds": 60},
            "mode": "alert",
            "cooldown_minutes": 20,
        }],
        "steps": [{
            "id": "s1", "label": "Abrir Chrome", "tool": "open_windows_app", "operation": "open",
            "params": {"app_name": "chrome"}, "delay_before": 0, "on_failure": "stop",
        }],
    }
    validated = validate_routine(payload)
    assert validated["triggers"][0]["type"] == "event"
    assert validated["triggers"][0]["event"] == "resource"
    assert validated["triggers"][0]["params"]["threshold"] == 92

    # Descreve gatilho em português
    desc = trig.describe_trigger(validated["triggers"][0])
    assert "CPU > 92%" in desc

    # Recusa se tentar encerrar processo com gatilho de evento
    payload_kill = {
        "name": "Matar programa em evento",
        "enabled": True,
        "triggers": [{
            "type": "event",
            "event": "app_started",
            "params": {"app_name": "notepad"},
            "mode": "run",
        }],
        "steps": [{
            "id": "s1", "label": "Fechar app", "tool": "open_windows_app", "operation": "close",
            "params": {"app_name": "notepad"}, "delay_before": 0, "on_failure": "stop",
        }],
    }
    with pytest.raises(RoutineError, match="Gatilho automático não pode encerrar programas"):
        validate_routine(payload_kill)


def test_event_watcher_tick_no_rules_no_probes_called(isolated_event_settings):
    # Desliga alertas globais e sem rotinas de evento
    runtime_settings.set_event_settings({
        "enabled": True,
        "cpu": {"enabled": False},
        "ram": {"enabled": False},
        "disk": {"enabled": False},
    })

    watcher = EventWatcher()
    cpu_calls = 0

    def mock_cpu():
        nonlocal cpu_calls
        cpu_calls += 1
        return 50.0

    watcher.probe_cpu = mock_cpu
    res = watcher.tick(datetime(2026, 11, 10, 10, 0, tzinfo=TZ))
    assert res == []
    assert cpu_calls == 0  # Zero sondas executadas sem regras


def test_event_watcher_global_resource_alert_and_recovery(isolated_event_settings):
    # Ativa alerta global de CPU acima de 90% por 20 segundos
    runtime_settings.set_event_settings({
        "enabled": True,
        "cooldown_minutes": 10,
        "cpu": {"enabled": True, "threshold": 90, "for_seconds": 20},
    })

    watcher = EventWatcher()
    current_cpu = 95.0
    watcher.probe_cpu = lambda: current_cpu

    t0 = datetime(2026, 11, 10, 10, 0, 0, tzinfo=TZ)
    # 1º tick: detecta alta mas duração = 0s (< 20s) -> não dispara
    res1 = watcher.tick(t0)
    assert res1 == []

    # 2º tick: t0 + 25s (duração 25s >= 20s) -> dispara alerta
    t1 = t0 + trig.timedelta(seconds=25)
    res2 = watcher.tick(t1)
    assert len(res2) == 1
    assert res2[0]["kind"] == "global_resource"
    assert res2[0]["metric"] == "cpu"

    # 3º tick: t0 + 35s ainda em alta, mas já disparou e em cooldown -> não repete
    t2 = t0 + trig.timedelta(seconds=35)
    res3 = watcher.tick(t2)
    assert res3 == []

    # 4º tick: CPU cai para 80% (abaixo de 90 - 5 = 85%) -> rearma
    current_cpu = 80.0
    t3 = t0 + trig.timedelta(seconds=60)
    watcher.tick(t3)
    assert "global:cpu" not in watcher._resource_triggered


def test_event_watcher_app_started_and_closed(isolated_event_settings):
    # Cria rotina de evento para app_started e app_closed
    store = EventWatcher.store()
    r1 = store.create({
        "name": "Spotify Aberto",
        "enabled": True,
        "triggers": [{"type": "event", "event": "app_started", "params": {"app_name": "spotify"}, "mode": "alert", "cooldown_minutes": 1}],
        "steps": [{"id": "s1", "label": "Abrir", "tool": "open_windows_app", "operation": "open", "params": {"app_name": "calc"}, "delay_before": 0, "on_failure": "stop"}],
    })
    r2 = store.create({
        "name": "Spotify Fechado",
        "enabled": True,
        "triggers": [{"type": "event", "event": "app_closed", "params": {"app_name": "spotify"}, "mode": "alert", "cooldown_minutes": 1}],
        "steps": [{"id": "s1", "label": "Abrir", "tool": "open_windows_app", "operation": "open", "params": {"app_name": "calc"}, "delay_before": 0, "on_failure": "stop"}],
    })

    watcher = EventWatcher()
    procs = {"chrome.exe", "explorer.exe"}
    watcher.probe_processes = lambda: set(procs)

    t0 = datetime(2026, 11, 10, 10, 0, 0, tzinfo=TZ)
    # 1º tick: primeiro tick apenas aprende o conjunto inicial
    res1 = watcher.tick(t0)
    assert res1 == []

    # 2º tick: spotify.exe entra
    procs.add("spotify.exe")
    t1 = t0 + trig.timedelta(seconds=15)
    res2 = watcher.tick(t1)
    assert len(res2) == 1
    assert res2[0]["kind"] == "routine_alert"
    assert res2[0]["routine_id"] == r1["id"]

    # 3º tick: spotify.exe sai
    procs.remove("spotify.exe")
    t2 = t0 + trig.timedelta(seconds=30)
    res3 = watcher.tick(t2)
    assert len(res3) == 1
    assert res3[0]["kind"] == "routine_alert"
    assert res3[0]["routine_id"] == r2["id"]


def test_event_watcher_calendar_before(isolated_event_settings):
    store = EventWatcher.store()
    r = store.create({
        "name": "Aviso Reunião",
        "enabled": True,
        "triggers": [{"type": "event", "event": "calendar_before", "params": {"minutes": 15}, "mode": "alert", "cooldown_minutes": 1}],
        "steps": [{"id": "s1", "label": "Etapa", "tool": "open_windows_app", "operation": "open", "params": {"app_name": "calc"}, "delay_before": 0, "on_failure": "stop"}],
    })

    event_time = datetime(2026, 11, 10, 10, 30, tzinfo=TZ)
    dummy_event = DummyCalendarEvent(id="ev_123", title="Reunião de Equipe", start=event_time)

    watcher = EventWatcher()
    watcher.probe_calendar_events = lambda start, end: [dummy_event]

    # Agora são 10:00 (30 min antes) -> ainda não dispara
    t0 = datetime(2026, 11, 10, 10, 0, tzinfo=TZ)
    res0 = watcher.tick(t0)
    assert res0 == []

    # Agora são 10:18 (12 min antes <= 15 min) -> dispara!
    t1 = datetime(2026, 11, 10, 10, 18, tzinfo=TZ)
    res1 = watcher.tick(t1)
    assert len(res1) == 1
    assert res1[0]["routine_id"] == r["id"]

    # Próximo tick -> não dispara repetido para o mesmo evento
    res2 = watcher.tick(t1 + trig.timedelta(seconds=10))
    assert res2 == []


def test_event_watcher_idle_and_returned(isolated_event_settings):
    store = EventWatcher.store()
    r_idle = store.create({
        "name": "Fui Ausente",
        "enabled": True,
        "triggers": [{"type": "event", "event": "idle", "params": {"minutes": 10}, "mode": "alert", "cooldown_minutes": 1}],
        "steps": [{"id": "s1", "label": "Etapa", "tool": "open_windows_app", "operation": "open", "params": {"app_name": "calc"}, "delay_before": 0, "on_failure": "stop"}],
    })
    r_return = store.create({
        "name": "Voltei ao PC",
        "enabled": True,
        "triggers": [{"type": "event", "event": "returned", "params": {}, "mode": "alert", "cooldown_minutes": 1}],
        "steps": [{"id": "s1", "label": "Etapa", "tool": "open_windows_app", "operation": "open", "params": {"app_name": "calc"}, "delay_before": 0, "on_failure": "stop"}],
    })

    idle_sec = 0.0
    watcher = EventWatcher()
    watcher.probe_idle_seconds = lambda: idle_sec

    # Usuário ativo
    t0 = datetime(2026, 11, 10, 14, 0, tzinfo=TZ)
    assert watcher.tick(t0) == []

    # Ocioso por 12 min (720s >= 10 min) -> dispara idle
    idle_sec = 720.0
    t1 = t0 + trig.timedelta(minutes=12)
    res_idle = watcher.tick(t1)
    assert any(x["routine_id"] == r_idle["id"] for x in res_idle)

    # Usuário mexe no mouse (idle_sec = 2s) -> detecta retorno
    idle_sec = 2.0
    t2 = t1 + trig.timedelta(seconds=15)
    res_return = watcher.tick(t2)
    assert any(x["routine_id"] == r_return["id"] for x in res_return)


def test_event_watcher_pause_and_resume(isolated_event_settings):
    runtime_settings.set_event_settings({
        "enabled": True,
        "cpu": {"enabled": True, "threshold": 50, "for_seconds": 0},
    })
    watcher = EventWatcher()
    watcher.probe_cpu = lambda: 99.0

    watcher.pause()
    assert watcher.tick(datetime(2026, 11, 10, 10, 0, tzinfo=TZ)) == []

    watcher.resume()
    res = watcher.tick(datetime(2026, 11, 10, 10, 0, tzinfo=TZ))
    assert len(res) == 1

