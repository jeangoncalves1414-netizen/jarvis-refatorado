"""Lote 7, pacote 4: cofre sem path traversal (MG10), água validada (MG17) e chaves mascaradas (MG14)."""
import http.client
import json
import sys
from contextlib import closing
from http.server import ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace

import pytest

from app.agent.tools.lifeos_tool import LifeOSTool
from app.agent.tools.memory_vault_tool import VaultDailyNoteTool, VaultSaveNoteTool, VaultUserProfileTool
from app.agent.tools.registry import ToolRegistry
from app.core.secrets_mask import mask_key, scrub_key
from app.services import memory_vault as vault_module
from app.services.lifeos import LifeOSService

KEY = "gsk_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789wxyz"


@pytest.fixture
def http_server(isolated_lote6_data, monkeypatch):
    from app.config import Settings
    from app.ui.panel import server

    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {tool.name: tool for tool in (LifeOSTool(), VaultSaveNoteTool(), VaultDailyNoteTool(), VaultUserProfileTool())}
    monkeypatch.setattr("app.agent.tools.registry.registry", registry)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.PanelHandler)
    monkeypatch.setattr(server.PanelHandler, "settings", Settings(host="127.0.0.1", port=httpd.server_address[1]))
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    def request(path, payload):
        with closing(http.client.HTTPConnection(*httpd.server_address, timeout=5)) as client:
            client.request("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
            res = client.getresponse()
            return res.status, json.loads(res.read().decode("utf-8"))

    try:
        yield SimpleNamespace(post=request, store=isolated_lote6_data.store, root=isolated_lote6_data.root)
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(2)


# ── MG10: /api/vault/notes ───────────────────────────────────────────────────

@pytest.mark.parametrize("folder", ["..", "../../Desktop", "05-Notas/../..", "..\\fora", "outra-pasta", 42])
def test_vault_notes_refuses_traversal_and_unknown_folders(http_server, folder):
    status, data = http_server.post("/api/vault/notes", {"title": "x", "content": "y", "folder": folder})
    assert status == 400 and data["ok"] is False
    assert not (http_server.root / "Desktop").exists()
    assert not list(http_server.root.glob("*.md")) and not list((http_server.root / "vault").glob("**/x.md"))
    assert http_server.store.list(limit=10) == []


def test_vault_notes_refuses_absolute_path(http_server):
    outside = http_server.root / "fora_do_cofre"
    status, data = http_server.post("/api/vault/notes", {"title": "x", "content": "y", "folder": str(outside)})
    assert status == 400 and data["ok"] is False
    assert not outside.exists()
    status, data = http_server.post("/api/vault/notes", {"title": "x", "content": "y", "folder": "C:\\Windows\\Temp"})
    assert status == 400


def test_vault_notes_saves_inside_the_vault_through_the_kernel(http_server):
    status, data = http_server.post("/api/vault/notes", {"title": "Ideias do dia", "content": "uma ideia", "folder": "05-Notas"})
    assert status == 200 and data["ok"] is True and data["path"] == "05-Notas/Ideias-do-dia.md"
    assert (http_server.root / "vault" / "05-Notas" / "Ideias-do-dia.md").is_file()
    run = http_server.store.run_page(include_reads=True)["runs"][0]
    assert run["origin"] == "window"
    assert [a.tool_name for a in http_server.store.list(limit=5)] == ["vault_save_note"]


def test_vault_notes_default_folder_is_projects(http_server):
    status, data = http_server.post("/api/vault/notes", {"title": "Projeto", "content": "texto"})
    assert status == 200 and data["path"] == "04-Projects/Projeto.md"


def test_vault_daily_log_and_profile_fact_go_through_the_kernel(http_server):
    assert http_server.post("/api/vault/daily/log", {"entry": "estudei", "category": "Aprendizado"})[0] == 200
    assert http_server.post("/api/vault/profile/fact", {"fact": "Prefere café sem açúcar"})[0] == 200
    assert http_server.post("/api/vault/daily/log", {"entry": "   "})[0] == 400
    assert http_server.post("/api/vault/desconhecida", {})[0] == 400
    assert {a.tool_name for a in http_server.store.list(limit=10)} == {"vault_daily_log", "vault_update_profile"}


def test_memory_vault_save_note_itself_refuses_folders_outside_the_vault(isolated_lote6_data):
    with pytest.raises(ValueError):
        vault_module.memory_vault.save_note("x", "y", folder="../fora")
    assert not (isolated_lote6_data.root / "fora").exists()


def test_dead_fastapi_vault_router_is_gone():
    with pytest.raises(ModuleNotFoundError):
        __import__("app.ui.panel.api.vault")


# ── MG17: /api/evolute/water/add ─────────────────────────────────────────────

@pytest.mark.parametrize("amount", [-5000, 0, 5001, 10_000_000, "abc", "nan", True, [250], {"ml": 1}])
def test_water_add_rejects_invalid_amounts(http_server, amount):
    LifeOSService.set_water(500)
    payload = {"amount_ml": amount}
    status, data = http_server.post("/api/evolute/water/add", payload)
    assert status == 400 and data["ok"] is False and "1 a 5000" in data["error"]
    assert LifeOSService.get_daily_summary()["water"]["current_ml"] == 500
    assert http_server.store.list(limit=10) == []


def test_water_add_valid_goes_through_the_kernel(http_server):
    LifeOSService.set_water(500)
    status, data = http_server.post("/api/evolute/water/add", {"amount_ml": 5000})
    assert status == 200 and data["added_ml"] == 5000 and data["total_ml"] == 5500
    assert data["popup"]["origin"] == "command"
    assert data["action"]["tool_name"] == "lifeos_tool" and data["action"]["status"] == "succeeded"
    assert http_server.store.run_page(include_reads=True)["runs"][0]["origin"] == "window"
    status, data = http_server.post("/api/evolute/water/add", {})
    assert status == 200 and data["added_ml"] == 250


# ── MG14: máscara de chaves ──────────────────────────────────────────────────

def test_mask_key_shows_only_the_last_four_characters():
    assert mask_key(KEY) == "…wxyz"
    assert KEY[:8] not in mask_key(KEY)
    assert mask_key("curta") == "…" and mask_key("") == "…" and mask_key(None) == "…"
    assert scrub_key(f"Incorrect API key provided: {KEY}.", KEY) == "Incorrect API key provided: …wxyz."


def test_key_rotator_cooldown_log_does_not_leak_the_key_prefix(capsys):
    from app.services.llm import KeyRotator

    KeyRotator().mark_cooldown(KEY, 1)
    out = capsys.readouterr().out
    assert "…wxyz" in out and KEY[:8] not in out and KEY not in out


def test_stt_groq_failure_log_masks_the_key(monkeypatch, tmp_path, capsys):
    from app.services.voice.stt.engine import STTEngine

    class FakeGroq:
        def __init__(self, api_key):
            raise RuntimeError(f"401 invalid key {api_key}")

    monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))
    engine = STTEngine.__new__(STTEngine)
    engine.groq_api_keys = [KEY]
    engine.language = "pt-BR"
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"x")
    assert engine._transcribe_groq(str(audio)) is None
    out = capsys.readouterr().out
    assert "…wxyz" in out and KEY[:8] not in out and KEY not in out
