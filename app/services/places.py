"""Busca de lugares (lote 6, Fase 5): OpenStreetMap/Nominatim por padrão, Google Places opcional.

Nominatim segue a política de uso pública: ``User-Agent`` próprio do app, no máximo uma
requisição por segundo (trava global), cache em memória e nada de autocompletar (só busca
quando a usuária envia). O ``email`` de contato é opcional (configuração ``places.email`` ou
variável ``NOMINATIM_EMAIL``).

Google Places (API New, Text Search) só é usado quando há chave ``google_places`` configurada;
se o Google falhar, a busca cai no OpenStreetMap e o resultado diz isso. A chave nunca vai
para o resultado nem para mensagens de erro.

Erro de rede vira ``ok: False`` com o motivo; nunca uma lista vazia fingindo sucesso.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Any

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GOOGLE_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_FIELD_MASK = "places.displayName,places.formattedAddress,places.location,places.rating,places.primaryType"
USER_AGENT = "JarvisPessoal/0.1 (uso pessoal; desktop)"
OSM_ATTRIBUTION = "© colaboradores do OpenStreetMap"
GOOGLE_ATTRIBUTION = "Dados do Google Maps"
MAX_QUERY = 120
MAX_NEAR = 80
MAX_RESULTS = 8
TIMEOUT_SECONDS = 8
MIN_INTERVAL_SECONDS = 1.0
CACHE_MAX = 100
CACHE_TTL_SECONDS = 24 * 3600
_BBOX_PADDING = 0.01

# Relógio e espera substituíveis nos testes (nenhuma rede nem espera real).
_clock = time.monotonic
_sleep = time.sleep

_rate_lock = threading.Lock()
_last_request_at: float | None = None
_cache_lock = threading.Lock()
_cache: "OrderedDict[str, tuple[float, dict[str, Any]]]" = OrderedDict()


class PlacesError(Exception):
    """Falha ao consultar o provedor de mapas (mensagem em pt-BR, sem segredos)."""


def clear_cache() -> None:
    global _last_request_at
    with _cache_lock:
        _cache.clear()
    with _rate_lock:
        _last_request_at = None


def _normalize(text: str) -> str:
    return " ".join(text.split()).lower()


def search_key(query: str, near: str = "") -> str:
    """Chave estável da busca (cache e chave do popup)."""
    raw = f"{_normalize(query)}|{_normalize(near)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def validate_search(query: Any, near: Any = "") -> tuple[str, str]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Informe o que procurar (ex.: padaria, farmácia 24h, Rua Augusta 100).")
    if len(query.strip()) > MAX_QUERY:
        raise ValueError(f"A busca deve ter no máximo {MAX_QUERY} caracteres.")
    if near is None:
        near = ""
    if not isinstance(near, str):
        raise ValueError("O campo 'perto de' deve ser texto.")
    if len(near.strip()) > MAX_NEAR:
        raise ValueError(f"O campo 'perto de' deve ter no máximo {MAX_NEAR} caracteres.")
    return " ".join(query.split()), " ".join(near.split())


def _contact_email() -> str:
    try:
        from app.storage.runtime_settings import get_places_settings

        email = get_places_settings().get("email", "")
    except Exception:
        email = ""
    return email or os.getenv("NOMINATIM_EMAIL", "").strip()


def _google_key() -> str:
    try:
        from app.storage.runtime_settings import get_api_keys

        raw = get_api_keys().get("google_places", "")
    except Exception:
        raw = ""
    raw = raw or os.getenv("GOOGLE_PLACES_API_KEY", "")
    return next((key.strip() for key in raw.replace("\n", ",").split(",") if key.strip()), "")


def _throttle() -> None:
    """Garante no mínimo 1 s entre requisições ao Nominatim. Chamar com ``_rate_lock`` tomado."""
    global _last_request_at
    if _last_request_at is not None:
        wait = MIN_INTERVAL_SECONDS - (_clock() - _last_request_at)
        if wait > 0:
            _sleep(wait)
    _last_request_at = _clock()


def _read_json(request: urllib.request.Request) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise PlacesError(f"o serviço respondeu HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        reason = getattr(exc, "reason", exc)
        raise PlacesError(f"sem conexão com o serviço de mapas ({type(reason).__name__ if not isinstance(reason, str) else reason})") from None
    except (ValueError, UnicodeDecodeError):
        raise PlacesError("o serviço de mapas devolveu uma resposta inválida") from None


def _float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # descarta NaN


def _bbox_for(results: list[dict[str, Any]], boxes: list[list[float]] | None = None) -> list[float] | None:
    """bbox no formato do mapa embutido do OSM: [oeste, sul, leste, norte]."""
    if boxes:
        west = min(box[0] for box in boxes)
        south = min(box[1] for box in boxes)
        east = max(box[2] for box in boxes)
        north = max(box[3] for box in boxes)
    elif results:
        west = min(item["lon"] for item in results) - _BBOX_PADDING
        south = min(item["lat"] for item in results) - _BBOX_PADDING
        east = max(item["lon"] for item in results) + _BBOX_PADDING
        north = max(item["lat"] for item in results) + _BBOX_PADDING
    else:
        return None
    return [round(west, 6), round(south, 6), round(east, 6), round(north, 6)]


def _search_osm(query: str, near: str) -> dict[str, Any]:
    params = {
        "format": "jsonv2",
        "addressdetails": "1",
        "limit": str(MAX_RESULTS),
        "accept-language": "pt-BR",
        "q": f"{query}, {near}" if near else query,
    }
    email = _contact_email()
    if email:
        params["email"] = email
    url = f"{NOMINATIM_URL}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with _rate_lock:
        _throttle()
        payload = _read_json(request)
    if not isinstance(payload, list):
        raise PlacesError("o OpenStreetMap devolveu uma resposta inválida")
    results: list[dict[str, Any]] = []
    boxes: list[list[float]] = []
    for item in payload[:MAX_RESULTS]:
        if not isinstance(item, dict):
            continue
        lat, lon = _float(item.get("lat")), _float(item.get("lon"))
        if lat is None or lon is None:
            continue
        address = str(item.get("display_name") or "").strip()
        name = str(item.get("name") or "").strip() or address.split(",")[0].strip()
        results.append({
            "name": name[:120] or "Sem nome",
            "address": address[:300],
            "lat": lat,
            "lon": lon,
            "category": str(item.get("type") or item.get("category") or "")[:60],
        })
        box = item.get("boundingbox")
        if isinstance(box, list) and len(box) == 4:
            south, north, west, east = (_float(value) for value in box)
            if None not in (south, north, west, east):
                boxes.append([west, south, east, north])  # type: ignore[list-item]
    return {"provider": "osm", "results": results, "bbox": _bbox_for(results, boxes), "attribution": OSM_ATTRIBUTION}


def _search_google(query: str, near: str, key: str) -> dict[str, Any]:
    body = json.dumps({
        "textQuery": f"{query} perto de {near}" if near else query,
        "languageCode": "pt-BR",
        "maxResultCount": MAX_RESULTS,
    }).encode("utf-8")
    request = urllib.request.Request(
        GOOGLE_TEXT_SEARCH_URL,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": GOOGLE_FIELD_MASK,
        },
    )
    payload = _read_json(request)
    if not isinstance(payload, dict):
        raise PlacesError("o Google devolveu uma resposta inválida")
    results: list[dict[str, Any]] = []
    for place in (payload.get("places") or [])[:MAX_RESULTS]:
        if not isinstance(place, dict):
            continue
        location = place.get("location") if isinstance(place.get("location"), dict) else {}
        lat, lon = _float(location.get("latitude")), _float(location.get("longitude"))
        if lat is None or lon is None:
            continue
        display = place.get("displayName") if isinstance(place.get("displayName"), dict) else {}
        item: dict[str, Any] = {
            "name": str(display.get("text") or "Sem nome")[:120],
            "address": str(place.get("formattedAddress") or "")[:300],
            "lat": lat,
            "lon": lon,
            "category": str(place.get("primaryType") or "")[:60],
        }
        rating = _float(place.get("rating"))
        if rating is not None:
            item["rating"] = round(rating, 1)
        results.append(item)
    return {"provider": "google", "results": results, "bbox": _bbox_for(results), "attribution": GOOGLE_ATTRIBUTION}


def cached_search(query: str, near: str = "") -> dict[str, Any] | None:
    """Resultado guardado para a mesma busca (até 24 h), sem rede. None se não houver."""
    key = search_key(query, near)
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        stored_at, result = entry
        if _clock() - stored_at > CACHE_TTL_SECONDS:
            _cache.pop(key, None)
            return None
        _cache.move_to_end(key)
        return {**result, "cached": True}


def _remember(query: str, near: str, result: dict[str, Any]) -> None:
    key = search_key(query, near)
    with _cache_lock:
        _cache[key] = (_clock(), result)
        _cache.move_to_end(key)
        while len(_cache) > CACHE_MAX:
            _cache.popitem(last=False)


def search_places(query: Any, near: Any = "") -> dict[str, Any]:
    """Procura lugares. Devolve ``ok``, ``provider`` (osm/google), ``results`` e ``bbox``."""
    try:
        query, near = validate_search(query, near)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    cached = cached_search(query, near)
    if cached is not None:
        return cached

    base = {"query": query, "near": near, "key": search_key(query, near)}
    google_error = ""
    found: dict[str, Any] | None = None
    google_key = _google_key()
    if google_key:
        try:
            found = _search_google(query, near, google_key)
        except PlacesError as exc:
            google_error = str(exc)
    if found is None:
        try:
            found = _search_osm(query, near)
        except PlacesError as exc:
            message = f"Não foi possível buscar lugares: {exc}."
            if google_error:
                message = f"Não foi possível buscar lugares: o Google Places falhou ({google_error}) e o OpenStreetMap também ({exc})."
            return {"ok": False, "error": message, "provider": "osm", **base}
    result = {"ok": True, **base, **found, "cached": False}
    if google_error:
        result["notice"] = f"O Google Places falhou ({google_error}); usei o OpenStreetMap."
    _remember(query, near, result)
    return result
