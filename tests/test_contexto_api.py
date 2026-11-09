"""Fase contexto 1: rotas GET/POST /api/settings/context."""
import json

from app.storage import runtime_settings
from app.storage.contexto_settings import CONTEXT_DEFAULTS
from app.ui.panel.api.contexto import handle_contexto_get, handle_contexto_post


def post(payload):
    return handle_contexto_post("/api/settings/context", json.dumps(payload).encode("utf-8"), None)


def test_get_returns_defaults(isolated_lote6_data):
    status, data = handle_contexto_get(["api", "settings", "context"], None)
    assert status == 200 and data == {"ok": True, "settings": CONTEXT_DEFAULTS}
    assert handle_contexto_get(["api", "settings", "popups"], None) is None


def test_post_saves_valid_settings(isolated_lote6_data):
    status, data = post({"settings": {"send_window_titles": True, "sources": {"window": False}}})
    assert status == 200 and data["settings"]["send_window_titles"] is True
    assert data["settings"]["sources"]["window"] is False
    assert runtime_settings._read()["situational_context"]["sources"]["window"] is False


def test_post_invalid_value_is_400_and_nothing_saved(isolated_lote6_data):
    status, data = post({"enabled": "talvez"})
    assert status == 400 and data["ok"] is False and "Usar contexto" in data["error"]
    status, data = post({"sources": {"pc": "não"}})
    assert status == 400
    assert "situational_context" not in runtime_settings._read()
    status, data = handle_contexto_post("/api/settings/context", b"{nope", None)
    assert status == 400 and data["error"] == "JSON inválido."
    assert handle_contexto_post("/api/settings/popups", b"{}", None) is None
