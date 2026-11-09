"""Conector opcional do Home Assistant (fase contexto 3).

REST do HA com ``Authorization: Bearer <token>``, timeout de 5 s, só ``urllib.request``.
Sem URL e token configurados, nada aqui chama a rede e a ferramenta ``home`` nem é oferecida
ao modelo. O token nunca entra em mensagem de erro nem em log: toda mensagem passa por ``_safe``.
Cada chamada real alimenta a saúde da integração (``capability_health``, id ``home_assistant``).
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from app.agent.tools.lifestyle_tools import normalize_name
from app.storage import contexto_settings

CAPABILITY = "home_assistant"
TIMEOUT = 3
CACHE_TTL = 60.0
NO_AREA = "Sem cômodo"
ENTITY_ID = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")
_AREA_TEMPLATE = "{% for s in states %}{{ s.entity_id }}|{{ area_name(s.entity_id) or '' }}\n{% endfor %}"

# Domínios com serviço próprio de ligar/desligar/alternar; os demais usam ``homeassistant.<op>``.
_NATIVE_ONOFF = frozenset({
    "light", "switch", "fan", "input_boolean", "media_player", "climate", "humidifier",
    "automation", "siren", "remote", "water_heater",
})
_SPECIAL_SERVICES = {
    ("cover", "turn_on"): "open_cover", ("cover", "turn_off"): "close_cover", ("cover", "toggle"): "toggle",
    ("lock", "turn_on"): "lock", ("lock", "turn_off"): "unlock",
    ("scene", "turn_on"): "turn_on", ("script", "turn_on"): "turn_on",
}

_clock = time.monotonic
_lock = threading.Lock()
_cache: dict[str, Any] = {"url": None, "at": 0.0, "entities": []}


class HomeAssistantError(RuntimeError):
    """Falha ao falar com o Home Assistant; a mensagem já está em português e sem token."""


def _config() -> dict[str, str]:
    return contexto_settings.get_home_assistant()


def is_configured() -> bool:
    try:
        current = _config()
        return bool(current["url"] and current["token"])
    except Exception:
        return False


def _host(url: str) -> str:
    return urllib.parse.urlsplit(url).netloc or url


def _safe(message: str, token: str | None = None) -> str:
    token = token if token is not None else _config().get("token", "")
    text = str(message)
    if token:
        text = text.replace(token, "••••")
    return text[:300]


def _health_success(latency_ms: int) -> None:
    try:
        from app.core.capability_health import capability_health
        capability_health.record_success(CAPABILITY, provider="home_assistant", latency_ms=latency_ms)
    except Exception:
        pass


def _health_failure(reason: str) -> None:
    try:
        from app.core.capability_health import capability_health
        capability_health.record_failure(CAPABILITY, provider="home_assistant", reason=reason)
    except Exception:
        pass


def _request(method: str, path: str, body: Any = None, *, raw: bool = False) -> Any:
    current = _config()
    url, token = current["url"], current["token"]
    if not (url and token):
        raise HomeAssistantError("Desligado: Home Assistant não configurado.")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url + path, data=data, method=method,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            payload = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            message = "Token do Home Assistant recusado."
            _health_failure(message)
        elif exc.code == 404:
            # O HA respondeu: alcançável, só não achou a entidade ou o serviço.
            _health_success(max(1, int((time.monotonic() - started) * 1000)))
            message = "Entidade ou serviço não encontrado no Home Assistant."
        elif exc.code == 400:
            _health_success(max(1, int((time.monotonic() - started) * 1000)))
            message = "O Home Assistant recusou o pedido (dados inválidos para este aparelho)."
        else:
            message = f"O Home Assistant respondeu com erro HTTP {exc.code}."
            _health_failure(message)
        raise HomeAssistantError(_safe(message, token)) from None
    except (urllib.error.URLError, OSError, TimeoutError):
        message = f"Home Assistant fora do ar em {_host(url)}."
        _health_failure(message)
        raise HomeAssistantError(_safe(message, token)) from None
    _health_success(max(1, int((time.monotonic() - started) * 1000)))
    if raw:
        return payload
    try:
        return json.loads(payload or "null")
    except json.JSONDecodeError:
        raise HomeAssistantError("O Home Assistant devolveu uma resposta inválida.") from None


def ping() -> dict[str, Any]:
    """Testa o alcance (``GET /api/``). Nunca levanta."""
    if not is_configured():
        return {"ok": False, "configured": False, "error": "Desligado: Home Assistant não configurado."}
    host = _host(_config()["url"])
    try:
        payload = _request("GET", "/api/")
    except HomeAssistantError as exc:
        return {"ok": False, "configured": True, "error": str(exc)}
    if isinstance(payload, dict) and payload.get("message"):
        return {"ok": True, "configured": True, "message": f"Conectado ao Home Assistant em {host}."}
    return {"ok": False, "configured": True, "error": f"O endereço {host} respondeu, mas não parece ser o Home Assistant."}


def _areas() -> dict[str, str]:
    try:
        text = _request("POST", "/api/template", {"template": _AREA_TEMPLATE}, raw=True)
    except HomeAssistantError:
        return {}
    areas: dict[str, str] = {}
    for line in str(text or "").splitlines():
        entity_id, sep, area = line.strip().partition("|")
        if sep and entity_id:
            areas[entity_id.strip()] = area.strip()
    return areas


def _entity(item: dict[str, Any], areas: dict[str, str]) -> dict[str, Any] | None:
    entity_id = str(item.get("entity_id") or "")
    if not ENTITY_ID.match(entity_id):
        return None
    attributes = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
    name = str(attributes.get("friendly_name") or entity_id.split(".", 1)[1].replace("_", " "))
    return {
        "entity_id": entity_id, "name": name[:120], "domain": entity_id.split(".", 1)[0],
        "state": str(item.get("state") or "")[:60], "area": areas.get(entity_id) or NO_AREA,
    }


def list_entities(force: bool = False) -> list[dict[str, Any]]:
    """Entidades do HA (cache de 60 s por endereço), com o cômodo de cada uma."""
    url = _config()["url"]
    with _lock:
        if not force and _cache["url"] == url and _cache["entities"] and _clock() - _cache["at"] < CACHE_TTL:
            return [dict(item) for item in _cache["entities"]]
    states = _request("GET", "/api/states")
    if not isinstance(states, list):
        raise HomeAssistantError("O Home Assistant devolveu uma lista de entidades inválida.")
    areas = _areas()
    entities = [entity for item in states if isinstance(item, dict) and (entity := _entity(item, areas))]
    entities.sort(key=lambda item: (item["area"] == NO_AREA, normalize_name(item["area"]), item["domain"], normalize_name(item["name"])))
    with _lock:
        _cache.update(url=url, at=_clock(), entities=entities)
    return [dict(item) for item in entities]


def clear_cache() -> None:
    with _lock:
        _cache.update(url=None, at=0.0, entities=[])


def get_state(entity_id: str) -> dict[str, Any]:
    if not ENTITY_ID.match(entity_id or ""):
        raise HomeAssistantError("Entidade inválida.")
    payload = _request("GET", f"/api/states/{entity_id}")
    if not isinstance(payload, dict):
        raise HomeAssistantError("O Home Assistant devolveu um estado inválido.")
    area = next((item["area"] for item in _cached() if item["entity_id"] == entity_id), NO_AREA)
    entity = _entity(payload, {entity_id: area}) or {"entity_id": entity_id, "state": ""}
    attributes = payload.get("attributes") if isinstance(payload.get("attributes"), dict) else {}
    extra = {key: attributes[key] for key in ("brightness", "temperature", "current_temperature", "unit_of_measurement") if key in attributes}
    return {**entity, "attributes": extra}


def call_service(domain: str, service: str, data: dict[str, Any]) -> Any:
    if not re.match(r"^[a-z_]+$", domain or "") or not re.match(r"^[a-z_]+$", service or ""):
        raise HomeAssistantError("Serviço do Home Assistant inválido.")
    entity_id = data.get("entity_id")
    if entity_id is not None and not ENTITY_ID.match(str(entity_id)):
        raise HomeAssistantError("Entidade inválida.")
    result = _request("POST", f"/api/services/{domain}/{service}", data)
    # O estado mudou: a próxima listagem busca de novo.
    clear_cache()
    return result


def service_for(domain: str, operation: str) -> tuple[str, str]:
    """Serviço de ligar/desligar/alternar para o domínio da entidade."""
    special = _SPECIAL_SERVICES.get((domain, operation))
    if special:
        return domain, special
    if domain in _NATIVE_ONOFF:
        return domain, operation
    return "homeassistant", operation


def _cached() -> list[dict[str, Any]]:
    with _lock:
        return [dict(item) for item in _cache["entities"]]


def _match(entities: list[dict[str, Any]], query: str, domains: tuple[str, ...] | None) -> dict[str, Any] | None:
    pool = [item for item in entities if not domains or item["domain"] in domains]
    raw = (query or "").strip()
    if ENTITY_ID.match(raw.lower()):
        found = next((item for item in pool if item["entity_id"] == raw.lower()), None)
        if found:
            return found
    wanted = normalize_name(raw)
    if not wanted:
        raise ValueError("Diga qual aparelho ou entidade da casa.")
    for picker in (
        lambda item: normalize_name(item["name"]) == wanted,
        lambda item: normalize_name(item["entity_id"].split(".", 1)[1].replace("_", " ")) == wanted,
    ):
        hits = [item for item in pool if picker(item)]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            _ambiguous(raw, hits)
    hits = [item for item in pool if wanted in normalize_name(item["name"])]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        _ambiguous(raw, hits)
    return None


def _ambiguous(query: str, hits: list[dict[str, Any]]) -> None:
    options = ", ".join(f"{item['name']} ({item['entity_id']})" for item in hits[:5])
    raise ValueError(f"Mais de um aparelho combina com '{query[:60]}': {options}. Diga qual.")


def resolve(name_or_id: str, domains: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Acha a entidade pelo nome amigável em português (sem acento) ou pelo entity_id."""
    found = _match(list_entities(), name_or_id, domains)
    if found is None:
        raise ValueError(f"Não achei '{str(name_or_id)[:60]}' no Home Assistant.")
    return found


LOW_DOMAINS = frozenset({"light", "switch", "fan", "media_player", "scene", "input_boolean"})
CRITICAL_DOMAINS = frozenset({"lock", "alarm_control_panel"})


def target_risk(operation: str, entity: str) -> str:
    """Risco pelo alvo (catálogo ``home``): leitura fica observe; escrita sobe pelo domínio.

    Luz, tomada, ventilador, mídia e cena: low. Fechadura e alarme: critical. Clima, cortina,
    aspirador e o resto: high. Entidade não resolvida no cache: high (falha fechada).
    """
    if operation in ("list_entities", "get_state"):
        return "observe"
    domain = (resolve_cached(entity) or {}).get("domain")
    if domain in CRITICAL_DOMAINS:
        return "critical"
    if domain in LOW_DOMAINS:
        return "low"
    return "high"


def resolve_cached(name_or_id: str) -> dict[str, Any] | None:
    """Mesma resolução só com o cache (sem HTTP, mesmo vencido); usada para classificar o risco."""
    raw = str(name_or_id or "").strip().lower()
    try:
        found = _match(_cached(), str(name_or_id or ""), None)
    except ValueError:
        found = None
    if found is None and ENTITY_ID.match(raw):
        return {"entity_id": raw, "domain": raw.split(".", 1)[0]}
    return found
