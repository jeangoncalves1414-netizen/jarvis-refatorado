"""Testes unitários para o Módulo de Notificações Acionáveis do Windows (Toast).

Testa:
- Geração de XML do Toast Notification (Windows 10/11) com botões e deep-links.
- Serviço windows_notifications (send_notification, execute_notification_action).
- Ferramenta nativa notification (NotificationTool) e registro no Action Kernel.
- Endpoints HTTP (GET e POST /api/notifications/action, /test, /send).
- Integração de alertas acionáveis no EventWatcher (watcher.py).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools.catalog import TOOL_CATALOG, metadata_for
from app.agent.tools.notification_tool import NotificationTool
from app.agent.tools.registry import ToolRegistry
from app.routines.watcher import EventWatcher
from app.services.windows_notifications import (
    build_toast_xml,
    execute_notification_action,
    send_notification,
)
from app.storage import runtime_settings
from app.ui.panel.api.notifications import (
    handle_notifications_get,
    handle_notifications_post,
)


# =====================================================================
# 1. Testes de Geração de XML do Toast
# =====================================================================

def test_build_toast_xml_basic():
    xml = build_toast_xml(title="Alerta Jarvis", message="Uso de CPU elevado", sound=True)
    assert "<toast>" in xml or "<toast" in xml
    assert "<text>Alerta Jarvis</text>" in xml
    assert "<text>Uso de CPU elevado</text>" in xml
    assert '<audio silent="true"/>' not in xml


def test_build_toast_xml_escapes_special_characters():
    xml = build_toast_xml(
        title="Tom & Jerry <Review>",
        message='Teste com "aspas" & símbolos > 50%',
        sound=False,
    )
    assert "Tom &amp; Jerry &lt;Review&gt;" in xml
    assert 'Teste com &quot;aspas&quot; &amp; símbolos &gt; 50%' in xml
    assert '<audio silent="true"/>' in xml


def test_build_toast_xml_with_actions():
    actions = [
        {"label": "Ouvir Briefing", "action": "briefing"},
        {"label": "Beber Água (+300ml)", "action": "water", "amount": 300},
        {"label": "Abrir Link", "action": "open_link", "url": "https://meet.google.com/abc-defg-hij"},
    ]
    xml = build_toast_xml(
        title="Lembrete",
        message="Sua reunião começa em breve",
        actions=actions,
        base_url="http://127.0.0.1:8000",
    )
    assert "<actions>" in xml
    assert 'content="Ouvir Briefing"' in xml
    assert 'action=briefing' in xml
    assert 'content="Beber Água (+300ml)"' in xml
    assert 'action=water' in xml
    assert 'amount=300' in xml
    assert 'content="Abrir Link"' in xml
    assert 'arguments="https://meet.google.com/abc-defg-hij"' in xml
    assert 'activationType="protocol"' in xml


def test_build_toast_xml_urgency_scenario():
    xml_critical = build_toast_xml(title="Crítico", message="Atenção", urgency="critical")
    assert 'scenario="alarm"' in xml_critical

    xml_normal = build_toast_xml(title="Normal", message="Aviso", urgency="normal")
    assert 'scenario="alarm"' not in xml_normal


# =====================================================================
# 2. Testes de Envio de Notificação (send_notification)
# =====================================================================

def test_send_notification_disabled(monkeypatch):
    monkeypatch.setattr(
        runtime_settings,
        "get_notification_settings",
        lambda: {"enabled": False, "sound": True},
    )
    result = send_notification("Título", "Mensagem", sync=True)
    assert result is False


def test_send_notification_enabled_success(monkeypatch):
    monkeypatch.setattr(
        runtime_settings,
        "get_notification_settings",
        lambda: {"enabled": True, "sound": True},
    )

    mock_run = MagicMock()
    mock_run.returncode = 0
    with patch("subprocess.run", return_value=mock_run) as mock_sub:
        result = send_notification(
            title="Jarvis",
            message="Teste de envio",
            actions=[{"label": "OK", "action": "habits"}],
            sync=True,
        )
        assert result is True
        assert mock_sub.called
        args, kwargs = mock_sub.call_args
        assert args[0][0] == "powershell"
        assert "-EncodedCommand" in args[0]


# =====================================================================
# 3. Testes de Execução de Ações Interativas (execute_notification_action)
# =====================================================================

def test_execute_notification_action_water(monkeypatch):
    mock_add_water = MagicMock(return_value={"total_ml": 1200, "target_ml": 3000})
    monkeypatch.setattr("app.services.lifeos.LifeOSService.add_water", mock_add_water)

    res = execute_notification_action("water", {"amount": 300})
    assert res["ok"] is True
    assert "+300ml de água" in res["message"]
    mock_add_water.assert_called_once_with(300)


def test_execute_notification_action_briefing(monkeypatch):
    monkeypatch.setattr(
        "app.services.briefing.generate_morning_briefing",
        lambda: "Bom dia! Hoje temos 2 reuniões e foco total.",
    )

    res = execute_notification_action("briefing")
    assert res["ok"] is True
    assert "Briefing matinal" in res["message"]
    assert "Bom dia!" in res["text"]


def test_execute_notification_action_habits():
    res = execute_notification_action("habits")
    assert res["ok"] is True
    assert "LifeOS" in res["message"]


def test_execute_notification_action_open_link(monkeypatch):
    mock_open = MagicMock()
    monkeypatch.setattr("webbrowser.open", mock_open)

    res = execute_notification_action("open_link", {"url": "https://github.com"})
    assert res["ok"] is True
    assert res["url"] == "https://github.com"
    mock_open.assert_called_once_with("https://github.com")


def test_execute_notification_action_unknown():
    res = execute_notification_action("invalid_action_xyz")
    assert res["ok"] is False
    assert "desconhecida" in res["error"]


# =====================================================================
# 4. Testes de Endpoints HTTP (GET e POST)
# =====================================================================

def test_handle_notifications_post_action():
    body = json.dumps({"action": "water", "amount": 300}).encode("utf-8")
    with patch("app.services.lifeos.LifeOSService.add_water", return_value={"total_ml": 600, "target_ml": 3000}):
        status, data = handle_notifications_post("/api/notifications/action", body, None)
        assert status == 200
        assert data["ok"] is True
        assert data["action"] == "water"


def test_handle_notifications_post_invalid_json():
    status, data = handle_notifications_post("/api/notifications/action", b"{invalid json", None)
    assert status == 400
    assert data["ok"] is False


def test_handle_notifications_post_missing_action():
    body = json.dumps({}).encode("utf-8")
    status, data = handle_notifications_post("/api/notifications/action", body, None)
    assert status == 400
    assert data["ok"] is False


def test_handle_notifications_get_action():
    class DummyHandler:
        path = "/api/notifications/action?action=habits"
        headers = {"Accept": "application/json"}

    status, data = handle_notifications_get(["api", "notifications", "action"], DummyHandler())
    assert status == 200
    assert data["ok"] is True
    assert data["action"] == "habits"


def test_handle_notifications_get_action_html():
    class DummyHandlerHtml:
        path = "/api/notifications/action?action=water&amount=300"
        headers = {"Accept": "text/html,application/xhtml+xml"}

    with patch("app.services.lifeos.LifeOSService.add_water", return_value={"total_ml": 900, "target_ml": 3000}):
        status, body = handle_notifications_get(["api", "notifications", "action"], DummyHandlerHtml())
        assert status == 200
        assert isinstance(body, bytes)
        html_str = body.decode("utf-8")
        assert "<!DOCTYPE html>" in html_str
        assert "Jarvis" in html_str


# =====================================================================
# 5. Testes da Ferramenta NotificationTool no Action Kernel
# =====================================================================

def test_notification_tool_execution(monkeypatch):
    tool = NotificationTool()
    assert tool.name == "notification"

    monkeypatch.setattr("app.services.windows_notifications.send_notification", lambda **kwargs: True)

    res = tool.run(
        title="Aviso de Teste",
        message="Mensagem informativa",
        urgency="high",
        actions=[{"label": "Ouvir", "action": "briefing"}],
    )
    assert res["ok"] is True
    assert res["notification"]["title"] == "Aviso de Teste"
    assert res["notification"]["urgency"] == "high"
    assert len(res["notification"]["actions"]) == 1


def test_notification_tool_requires_message():
    tool = NotificationTool()
    res = tool.run(title="Sem Mensagem", message="")
    assert res["ok"] is False
    assert "obrigatória" in res["error"]


def test_notification_tool_in_catalog_and_registry():
    # Verifica catálogo de segurança (Action Kernel)
    meta = TOOL_CATALOG.get("notification")
    assert meta is not None
    assert meta.default_risk == "low"
    assert meta.reversible is True

    # Verifica registro de ferramentas do agente
    reg = ToolRegistry()
    tool = reg.get_tool("notification")
    assert tool is not None
    assert isinstance(tool, NotificationTool)


# =====================================================================
# 6. Testes de Integração com o EventWatcher (watcher.py)
# =====================================================================

def test_watcher_fires_actionable_notification_on_cpu_threshold(monkeypatch):
    watcher = EventWatcher()
    watcher.probe_cpu = lambda: 95.0
    watcher.probe_ram = lambda: 50.0
    watcher.probe_disk = lambda _path: 50.0

    monkeypatch.setattr(
        runtime_settings,
        "get_event_settings",
        lambda: {
            "enabled": True,
            "interval_seconds": 15,
            "cooldown_minutes": 0,
            "disk_path": "C:\\",
            "cpu": {"enabled": True, "threshold": 90, "for_seconds": 0},
            "ram": {"enabled": False, "threshold": 90, "for_seconds": 0},
            "disk": {"enabled": False, "threshold": 95, "for_seconds": 0},
        },
    )

    mock_send = MagicMock()
    monkeypatch.setattr("app.services.windows_notifications.send_notification", mock_send)

    dispatched = watcher.tick()
    assert any(d.get("kind") == "global_resource" and d.get("metric") == "cpu" for d in dispatched)
    assert mock_send.called
    kwargs = mock_send.call_args.kwargs
    assert "CPU" in kwargs["title"]
    assert kwargs["urgency"] == "high"
    assert any(a["action"] == "habits" for a in kwargs["actions"])
