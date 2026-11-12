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


# ------------------------------------------------------------ fase 3: Home Assistant e Casa

def ha_post(payload):
    return handle_contexto_post("/api/settings/home-assistant", json.dumps(payload).encode("utf-8"), None)


def home_action_post(payload):
    return handle_contexto_post("/api/home/action", json.dumps(payload).encode("utf-8"), None)


def test_ha_settings_and_test_routes(isolated_lote6_data, monkeypatch):
    from app.services import home_assistant as ha

    status, data = handle_contexto_get(["api", "settings", "home-assistant"], None)
    assert status == 200 and data["ok"] is True and data["settings"]["configured"] is False

    # POST com valores válidos
    status, data = ha_post({"url": "http://192.168.1.200:8123", "token": "meu_token_secreto_longo"})
    assert status == 200 and data["ok"] is True
    assert data["settings"]["configured"] is True
    assert data["settings"]["token_masked"] == "••••ongo"

    # POST com endereço inválido
    status, data = ha_post({"url": "endereco_sem_http"})
    assert status == 400 and data["ok"] is False

    # POST test rota
    monkeypatch.setattr(ha, "ping", lambda: {"ok": True, "configured": True, "message": "Conectado"})
    status, data = handle_contexto_post("/api/settings/home-assistant/test", b"{}", None)
    assert status == 200 and data["ok"] is True


def test_home_entities_and_action_routes(isolated_lote6_data, monkeypatch):
    from app.services import home_assistant as ha
    from app.storage import contexto_settings

    # Sem configuração
    status, data = handle_contexto_get(["api", "home", "entities"], None)
    assert status == 200 and data["configured"] is False and data["entities"] == []

    # Configura HA
    contexto_settings.set_home_assistant({"url": "http://192.168.1.200:8123", "token": "tok_12345678"})

    fake_entities = [
        {"entity_id": "light.sala", "name": "Luz da Sala", "domain": "light", "state": "off", "area": "Sala"},
        {"entity_id": "lock.porta", "name": "Fechadura", "domain": "lock", "state": "unlocked", "area": "Entrada"},
    ]
    monkeypatch.setattr(ha, "list_entities", lambda force=False: fake_entities)
    monkeypatch.setattr(ha, "resolve", lambda name, domains=None: next(e for e in fake_entities if e["entity_id"] == name or e["name"] == name))
    monkeypatch.setattr(ha, "resolve_cached", lambda name: next((e for e in fake_entities if e["entity_id"] == name or e["name"] == name), None))
    monkeypatch.setattr(ha, "call_service", lambda domain, service, data: [])

    # GET /api/home/entities via Kernel
    status, data = handle_contexto_get(["api", "home", "entities"], None)
    assert status == 200 and data["configured"] is True and len(data["entities"]) == 2

    # POST /api/home/action para light (baixo risco -> executa direto se permitido)
    status, data = home_action_post({"operation": "turn_on", "entity": "light.sala"})
    assert status == 200 and data["ok"] is True

    # POST /api/home/action para lock (crítico -> requer confirmação na Central)
    status, data = home_action_post({"operation": "turn_on", "entity": "lock.porta"})
    assert status == 200 and data["pending"] is True
    assert data["pending_action_id"] is not None


def test_delete_selected_memories_cleans_index_and_keeps_other_facts(isolated_lote6_data):
    from app.ui.panel.api.contexto import _facts_post
    from unittest.mock import Mock
    ids = [facts_post({"operation": "save", "text": text})[1]["fact"]["id"]
           for text in ("Gosto de azul", "Coleciono livros", "Tenho um gato")]
    index = Mock()
    status, result = _facts_post({"operation": "delete_many", "ids": [ids[0], ids[0], ids[1]]}, index)
    assert status == 200 and result["ids"] == ids[:2]
    assert index.delete_where.call_count == 2
    assert [f["id"] for f in handle_contexto_get(["api", "memories", "facts"], None)[1]["facts"]] == ids[2:]
