"""Testes do conector opcional do Home Assistant (fase contexto 3).

Totalmente isolado: nenhuma chamada de rede real (urllib.request.urlopen sempre mockado).
Usa isolated_lote6_data para isolar runtime_settings.
"""
from __future__ import annotations

import io
import json
import urllib.error
from types import SimpleNamespace
from typing import Any

import pytest

from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.home_tool import HomeTool
from app.agent.tools.registry import ToolRegistry
from app.core.capability_health import capability_health
from app.services import home_assistant as ha
from app.storage import contexto_settings


class FakeResponse(io.BytesIO):
    def __init__(self, data: bytes, status: int = 200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeHANetwork:
    def __init__(self):
        self.requests: list[SimpleNamespace] = []
        self.states: list[dict[str, Any]] = [
            {"entity_id": "light.sala", "state": "off", "attributes": {"friendly_name": "Luz da Sala", "brightness": 128}},
            {"entity_id": "light.quarto", "state": "on", "attributes": {"friendly_name": "Luz do Quarto"}},
            {"entity_id": "switch.cafeteira", "state": "off", "attributes": {"friendly_name": "Cafeteira"}},
            {"entity_id": "lock.porta_frente", "state": "locked", "attributes": {"friendly_name": "Fechadura Principal"}},
            {"entity_id": "climate.ar_quarto", "state": "cool", "attributes": {"friendly_name": "Ar Condicionado", "temperature": 22.0}},
            {"entity_id": "cover.persiana_sala", "state": "closed", "attributes": {"friendly_name": "Persiana da Sala"}},
            {"entity_id": "scene.cinema", "state": "scening", "attributes": {"friendly_name": "Modo Cinema"}},
            {"entity_id": "script.boa_noite", "state": "off", "attributes": {"friendly_name": "Rotina Boa Noite"}},
        ]
        self.areas_template_text = (
            "light.sala|Sala\n"
            "light.quarto|Quarto\n"
            "switch.cafeteira|Cozinha\n"
            "lock.porta_frente|Entrada\n"
            "climate.ar_quarto|Quarto\n"
            "cover.persiana_sala|Sala\n"
            "scene.cinema|\n"
        )
        self.fail_ping: Exception | None = None
        self.fail_states: Exception | None = None
        self.fail_template: Exception | None = None
        self.fail_service: Exception | None = None

    def __call__(self, request, timeout=None):
        url = request.full_url
        method = request.get_method()
        headers = {k.lower(): v for k, v in request.header_items()}
        body = json.loads(request.data.decode("utf-8")) if request.data else None
        self.requests.append(SimpleNamespace(url=url, method=method, headers=headers, body=body, timeout=timeout))

        if url.endswith("/api/"):
            if self.fail_ping:
                raise self.fail_ping
            return FakeResponse(json.dumps({"message": "API running."}).encode("utf-8"))

        if url.endswith("/api/states"):
            if self.fail_states:
                raise self.fail_states
            return FakeResponse(json.dumps(self.states).encode("utf-8"))

        if url.endswith("/api/template"):
            if self.fail_template:
                raise self.fail_template
            return FakeResponse(self.areas_template_text.encode("utf-8"))

        if "/api/states/" in url:
            entity_id = url.split("/api/states/", 1)[1]
            found = next((s for s in self.states if s["entity_id"] == entity_id), None)
            if not found:
                fp = io.BytesIO(b'{"message": "Entity not found"}')
                raise urllib.error.HTTPError(url, 404, "Not Found", {}, fp)
            return FakeResponse(json.dumps(found).encode("utf-8"))

        if "/api/services/" in url:
            if self.fail_service:
                raise self.fail_service
            return FakeResponse(b"[]")

        fp = io.BytesIO(b'{"message": "Not Found"}')
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, fp)


@pytest.fixture(autouse=True)
def setup_ha(isolated_lote6_data, monkeypatch):
    ha.clear_cache()
    capability_health.clear()
    fake_net = FakeHANetwork()
    monkeypatch.setattr(ha.urllib.request, "urlopen", fake_net)
    return fake_net


# ── 1. Configurações e mascaramento de token ──────────────────────────────────

def test_ha_url_validation():
    assert contexto_settings.normalize_ha_url("http://192.168.1.100:8123/") == "http://192.168.1.100:8123"
    assert contexto_settings.normalize_ha_url("https://homeassistant.local:8123") == "https://homeassistant.local:8123"
    assert contexto_settings.normalize_ha_url("") == ""

    with pytest.raises(ValueError, match="Não coloque usuário ou senha"):
        contexto_settings.normalize_ha_url("http://user:pass@192.168.1.100:8123")

    with pytest.raises(ValueError, match="Informe só o endereço"):
        contexto_settings.normalize_ha_url("http://192.168.1.100:8123/api/states")

    with pytest.raises(ValueError, match="inválid"):
        contexto_settings.normalize_ha_url("http://192.168.1.100:99999")


def test_ha_settings_storage():
    pub = contexto_settings.home_assistant_public()
    assert pub["configured"] is False
    assert pub["token_masked"] == ""

    saved = contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "secret_long_lived_token_12345",
    })
    assert saved["configured"] is True
    assert saved["url"] == "http://192.168.0.50:8123"
    assert saved["token_masked"] == "••••2345"

    # Atualizar url sem token mantém o token antigo
    saved2 = contexto_settings.set_home_assistant({"url": "http://192.168.0.51:8123"})
    assert saved2["url"] == "http://192.168.0.51:8123"
    assert saved2["token_masked"] == "••••2345"
    assert contexto_settings.get_home_assistant()["token"] == "secret_long_lived_token_12345"

    # Limpar apaga tudo
    cleared = contexto_settings.set_home_assistant({"clear": True})
    assert cleared["configured"] is False
    assert cleared["url"] == ""
    assert cleared["token_masked"] == ""


def test_ha_token_safety_in_errors():
    token = "SUPER_SECRET_TOKEN_XYZ987"
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": token,
    })
    safe_msg = ha._safe(f"Erro com o token {token} ao conectar.")
    assert token not in safe_msg
    assert "••••" in safe_msg


# ── 2. Ping e saúde de conexão ────────────────────────────────────────────────

def test_ping_success(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    res = ha.ping()
    assert res["ok"] is True
    assert res["configured"] is True
    assert "192.168.0.50:8123" in res["message"]


def test_ping_not_configured():
    res = ha.ping()
    assert res["ok"] is False
    assert res["configured"] is False
    assert "não configurado" in res["error"]


def test_ping_auth_failure(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "invalid_token_9999",
    })
    fp = io.BytesIO(b'{"message": "Unauthorized"}')
    setup_ha.fail_ping = urllib.error.HTTPError("http://192.168.0.50:8123/api/", 401, "Unauthorized", {}, fp)

    res = ha.ping()
    assert res["ok"] is False
    assert res["configured"] is True
    assert "Token do Home Assistant recusado" in res["error"]
    assert "invalid_token" not in res["error"]


# ── 3. Listagem de entidades, áreas e cache ───────────────────────────────────

def test_list_entities_with_areas_and_caching(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    entities = ha.list_entities()
    assert len(entities) == 8

    sala_light = next(e for e in entities if e["entity_id"] == "light.sala")
    assert sala_light["name"] == "Luz da Sala"
    assert sala_light["area"] == "Sala"
    assert sala_light["domain"] == "light"

    cinema_scene = next(e for e in entities if e["entity_id"] == "scene.cinema")
    assert cinema_scene["area"] == "Sem cômodo"

    # Segunda chamada não deve refazer requisições HTTP devido ao cache
    req_count_before = len(setup_ha.requests)
    entities_cached = ha.list_entities()
    assert len(setup_ha.requests) == req_count_before
    assert len(entities_cached) == 8

    # Forçando refresh refaz chamadas
    ha.list_entities(force=True)
    assert len(setup_ha.requests) > req_count_before


def test_list_entities_template_failure_fallback_to_no_area(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    setup_ha.fail_template = urllib.error.HTTPError("http://192.168.0.50:8123/api/template", 500, "Error", {}, io.BytesIO(b""))

    ha.clear_cache()
    entities = ha.list_entities()
    assert len(entities) == 8
    # Todas devem ter caído no fallback "Sem cômodo"
    assert all(e["area"] == "Sem cômodo" for e in entities)


# ── 4. Resolução de entidades (sem acento, case-insensitive, ambígua) ──────────

def test_resolve_entity(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    # Pelo entity_id
    assert ha.resolve("light.sala")["entity_id"] == "light.sala"

    # Pelo nome amigável sem acento
    assert ha.resolve("luz da sala")["entity_id"] == "light.sala"
    assert ha.resolve("cafeteira")["entity_id"] == "switch.cafeteira"
    assert ha.resolve("modo cinema")["entity_id"] == "scene.cinema"

    # Ambiguidade ("luz" combina com luz da sala e luz do quarto)
    with pytest.raises(ValueError, match="Mais de um aparelho"):
        ha.resolve("luz")

    # Inexistente
    with pytest.raises(ValueError, match="Não achei 'abajur'"):
        ha.resolve("abajur")


# ── 5. Classificação de Risco (target_risk) ───────────────────────────────────

def test_target_risk_classification(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    ha.list_entities()  # aquece o cache

    # Leitura é sempre observe
    assert ha.target_risk("list_entities", "light.sala") == "observe"
    assert ha.target_risk("get_state", "lock.porta_frente") == "observe"

    # Domínios de baixo risco
    assert ha.target_risk("turn_on", "light.sala") == "low"
    assert ha.target_risk("turn_off", "switch.cafeteira") == "low"
    assert ha.target_risk("run_scene", "scene.cinema") == "low"

    # Domínios críticos
    assert ha.target_risk("turn_on", "lock.porta_frente") == "critical"
    assert ha.target_risk("turn_on", "alarm_control_panel.casa") == "critical"

    # Domínios altos
    assert ha.target_risk("turn_on", "climate.ar_quarto") == "high"
    assert ha.target_risk("turn_on", "cover.persiana_sala") == "high"

    # Não encontrada no cache -> high (falha fechada)
    assert ha.target_risk("turn_on", "dispositivo_desconhecido") == "high"


# ── 6. Execução via HomeTool e ToolRegistry ───────────────────────────────────

def test_home_tool_not_configured():
    tool = HomeTool()
    res = tool.execute({"operation": "list_entities"})
    assert res.ok is False
    assert "não configurado" in res.message


def test_home_tool_list_entities(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    tool = HomeTool()

    # Listagem geral
    res = tool.execute({"operation": "list_entities"})
    assert res.ok is True
    assert "8 aparelho(s)" in res.message
    assert len(res.data["entities"]) == 8

    # Filtro por cômodo
    res_quarto = tool.execute({"operation": "list_entities", "area": "quarto"})
    assert res_quarto.ok is True
    assert len(res_quarto.data["entities"]) == 2


def test_home_tool_turn_on_and_special_services(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    tool = HomeTool()

    # Luz: light.turn_on
    res_light = tool.execute({"operation": "turn_on", "entity": "luz da sala"})
    assert res_light.ok is True
    assert "Ligado: Luz da Sala" in res_light.message
    assert setup_ha.requests[-1].url.endswith("/api/services/light/turn_on")

    # Fechadura: lock.lock
    res_lock = tool.execute({"operation": "turn_on", "entity": "fechadura principal"})
    assert res_lock.ok is True
    assert setup_ha.requests[-1].url.endswith("/api/services/lock/lock")

    # Cortina / Persiana: cover.close_cover para turn_off
    res_cover = tool.execute({"operation": "turn_off", "entity": "persiana da sala"})
    assert res_cover.ok is True
    assert setup_ha.requests[-1].url.endswith("/api/services/cover/close_cover")


def test_home_tool_set_brightness_and_temperature(setup_ha):
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })
    tool = HomeTool()

    # Brilho em luz
    res_bright = tool.execute({"operation": "set", "entity": "luz da sala", "brightness": 75})
    assert res_bright.ok is True
    assert "brilho em 75%" in res_bright.message
    assert setup_ha.requests[-1].body == {"entity_id": "light.sala", "brightness_pct": 75}

    # Brilho em não-luz deve falhar
    res_bad = tool.execute({"operation": "set", "entity": "cafeteira", "brightness": 50})
    assert res_bad.ok is False
    assert "Brilho só vale para luzes" in res_bad.message

    # Temperatura em ar condicionado
    res_temp = tool.execute({"operation": "set", "entity": "ar condicionado", "temperature": 21.5})
    assert res_temp.ok is True
    assert "temperatura em 21.5 °C" in res_temp.message
    assert setup_ha.requests[-1].body == {"entity_id": "climate.ar_quarto", "temperature": 21.5}


def test_home_tool_allowed_tools_filtering():
    registry = ToolRegistry()

    # Sem HA configurado: home NÃO pode aparecer em allowed_tool_names
    assert "home" not in registry.allowed_tool_names(mode="general")
    assert "home" not in registry.allowed_tool_names(mode="general", provider="groq", user_text="liga a luz")
    assert "home" not in registry.allowed_tool_names(mode="general", narrow=True, user_text="luz da sala")

    # Com HA configurado:
    contexto_settings.set_home_assistant({
        "url": "http://192.168.0.50:8123",
        "token": "valid_token_12345",
    })

    # Geral: oferecida
    assert "home" in registry.allowed_tool_names(mode="general")

    # Groq: entra com palavras de casa/luz
    assert "home" in registry.allowed_tool_names(mode="general", provider="groq", user_text="acenda a lampada")
    # Mas sem palavras-chave não entra no groq
    assert "home" not in registry.allowed_tool_names(mode="general", provider="groq", user_text="conte uma piada")


def test_catalog_home_metadata():
    meta = TOOL_CATALOG.get("home")
    assert meta is not None
    assert meta.default_operation == "list_entities"
    risks = dict(meta.operation_risks)
    assert risks.get("list_entities") == "observe"
    assert risks.get("get_state") == "observe"
    assert risks.get("turn_on") == "low"
    assert risks.get("run_script") == "high"
