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


# ------------------------------------------------------------ fase 2: memórias com fonte

def facts_post(payload):
    return handle_contexto_post("/api/memories/facts", json.dumps(payload).encode("utf-8"), None)


def test_facts_routes_save_update_delete_through_kernel(isolated_lote6_data):
    status, data = handle_contexto_get(["api", "memories", "facts"], None)
    assert status == 200 and data == {"ok": True, "facts": []}

    status, data = facts_post({"operation": "save", "text": "de manhã prefiro a playlist Foco"})
    assert status == 200 and data["ok"] and data["action"]["status"] == "succeeded"
    fact = data["fact"]
    assert fact["source"]["origin"] == "painel" and fact["source"]["kind"] == "manual" and fact["slot"] == "music"

    status, data = facts_post({"operation": "update", "id": fact["id"], "text": "eu moro em Recife"})
    assert status == 200 and data["fact"]["value"] == "Recife"
    status, data = handle_contexto_get(["api", "memories", "facts"], None)
    assert [f["text"] for f in data["facts"]] == ["eu moro em Recife"]

    status, data = facts_post({"operation": "delete", "id": fact["id"]})
    assert status == 200 and data["fact"]["deleted_at"]
    assert handle_contexto_get(["api", "memories", "facts"], None)[1]["facts"] == []

    actions = isolated_lote6_data.store.list()
    assert [a.tool_name for a in actions] == ["memory_tool"] * 3
    runs = {isolated_lote6_data.store.run_details(a.run_id)["run"]["origin"] for a in actions}
    assert runs == {"window"}


def test_facts_routes_reject_bad_input(isolated_lote6_data):
    assert facts_post({"operation": "save", "text": "  "})[0] == 400
    status, data = facts_post({"operation": "save", "text": "x" * 301})
    assert status == 400 and "300" in data["error"]
    status, data = facts_post({"operation": "update", "id": "mem_000", "text": "oi"})
    assert status == 400 and data["error"] == "Memória não encontrada."
    assert facts_post({"operation": "delete", "id": "mem_000"})[0] == 400
    assert facts_post({"operation": "drop"})[0] == 400
    assert handle_contexto_post("/api/memories/facts", b"{nope", None)[0] == 400
    assert isolated_lote6_data.store.list() == []
