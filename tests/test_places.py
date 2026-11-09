"""Busca de lugares (lote 6, Fase 5): OSM/Nominatim, Google Places opcional, rota e popup.

Nenhuma rede real: ``urllib.request.urlopen`` é trocado em todos os testes.
"""
import io
import json
import urllib.error
import urllib.parse
from types import SimpleNamespace

import pytest

from app.agent import popups
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.places_search import PlacesSearchTool
from app.agent.tools.registry import GENERAL_TOOL_NAMES, GROQ_KEYWORD_TOOLS, ToolRegistry
from app.core import ui_events
from app.core.runs import current_origin
from app.services import places
from app.storage import runtime_settings
from app.ui.panel.api import places as places_api
from app.ui.panel.api import popups as popups_api

GOOGLE_TEST_KEY = "test-google-key-not-real"

OSM_PAYLOAD = [
    {"name": "Padaria Central", "display_name": "Padaria Central, Rua A, 10, São Paulo", "lat": "-23.5500", "lon": "-46.6300",
     "type": "bakery", "boundingbox": ["-23.5510", "-23.5490", "-46.6310", "-46.6290"]},
    {"name": "", "display_name": "Padaria Bela Vista, Rua B, 20, São Paulo", "lat": "-23.5600", "lon": "-46.6400",
     "type": "bakery", "boundingbox": ["-23.5610", "-23.5590", "-46.6410", "-46.6390"]},
    {"name": "Sem coordenada", "display_name": "x"},
]
GOOGLE_PAYLOAD = {"places": [
    {"displayName": {"text": "Padaria Google"}, "formattedAddress": "Av. Paulista, 1000", "location": {"latitude": -23.56, "longitude": -46.65},
     "rating": 4.63, "primaryType": "bakery"},
]}


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class FakeNetwork:
    def __init__(self):
        self.requests = []
        self.osm = OSM_PAYLOAD
        self.google = GOOGLE_PAYLOAD
        self.fail_osm = None
        self.fail_google = None

    def __call__(self, request, timeout=None):
        self.requests.append(SimpleNamespace(
            url=request.full_url, method=request.get_method(), timeout=timeout,
            headers={key.lower(): value for key, value in request.header_items()},
            body=json.loads(request.data.decode("utf-8")) if request.data else None,
        ))
        if request.full_url.startswith(places.GOOGLE_TEXT_SEARCH_URL):
            if self.fail_google:
                raise self.fail_google
            return FakeResponse(json.dumps(self.google).encode("utf-8"))
        if self.fail_osm:
            raise self.fail_osm
        return FakeResponse(json.dumps(self.osm).encode("utf-8"))


@pytest.fixture
def net(isolated_lote6_data, monkeypatch):
    for name in ("GOOGLE_PLACES_API_KEY", "GOOGLE_PLACES_API_KEYS", "NOMINATIM_EMAIL"):
        monkeypatch.delenv(name, raising=False)
    fake = FakeNetwork()
    monkeypatch.setattr(places.urllib.request, "urlopen", fake)
    clock = {"now": 1000.0}
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock["now"] += seconds
    monkeypatch.setattr(places, "_clock", lambda: clock["now"])
    monkeypatch.setattr(places, "_sleep", sleep)
    places.clear_cache()
    fake.clock = clock
    fake.sleeps = sleeps
    fake.store = isolated_lote6_data.store
    yield fake
    places.clear_cache()


def _query(url):
    return dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(url).query))


def test_osm_request_follows_usage_policy(net):
    result = places.search_places("padaria", "Bela Vista")
    assert result["ok"] is True and result["provider"] == "osm"
    [request] = net.requests
    assert request.url.startswith(places.NOMINATIM_URL + "?")
    query = _query(request.url)
    assert query == {"format": "jsonv2", "addressdetails": "1", "limit": "8", "accept-language": "pt-BR", "q": "padaria, Bela Vista"}
    assert request.headers["user-agent"] == "JarvisPessoal/0.1 (uso pessoal; desktop)"
    assert request.timeout == 8
    # Item sem coordenada é descartado; nome vazio usa o começo do endereço.
    assert [item["name"] for item in result["results"]] == ["Padaria Central", "Padaria Bela Vista"]
    assert result["results"][0] == {"name": "Padaria Central", "address": "Padaria Central, Rua A, 10, São Paulo", "lat": -23.55, "lon": -46.63, "category": "bakery"}
    assert result["bbox"] == [-46.641, -23.561, -46.629, -23.549]
    assert result["attribution"] == "© colaboradores do OpenStreetMap"


def test_optional_contact_email_is_sent(net):
    runtime_settings._write({"places": {"email": "eu@example.com"}})
    places.search_places("farmácia")
    assert _query(net.requests[0].url)["email"] == "eu@example.com"


def test_same_search_comes_from_cache_without_network(net):
    first = places.search_places("padaria", "Bela Vista")
    second = places.search_places("  PADARIA ", "bela   vista")
    assert len(net.requests) == 1
    assert second["cached"] is True and second["results"] == first["results"]
    # Depois de 24 h a busca vai à rede de novo.
    net.clock["now"] += places.CACHE_TTL_SECONDS + 1
    places.search_places("padaria", "Bela Vista")
    assert len(net.requests) == 2


def test_two_different_searches_wait_at_least_one_second(net):
    places.search_places("padaria")
    net.clock["now"] += 0.3
    places.search_places("farmácia")
    assert len(net.requests) == 2
    assert net.sleeps and abs(net.sleeps[0] - 0.7) < 1e-9
    net.clock["now"] += 5
    places.search_places("mercado")
    assert len(net.sleeps) == 1  # já passou mais de 1 s: sem espera


def test_cache_keeps_at_most_100_searches(net):
    for index in range(places.CACHE_MAX + 1):
        places.search_places(f"lugar {index}")
    assert places.cached_search("lugar 0") is None
    assert places.cached_search(f"lugar {places.CACHE_MAX}") is not None


def test_without_key_uses_osm_and_with_key_uses_google_headers(net, monkeypatch):
    assert places.search_places("padaria")["provider"] == "osm"
    monkeypatch.setenv("GOOGLE_PLACES_API_KEYS", GOOGLE_TEST_KEY)
    result = places.search_places("padaria", "Paulista")
    assert result["ok"] is True and result["provider"] == "google"
    request = net.requests[-1]
    assert request.url == places.GOOGLE_TEXT_SEARCH_URL and request.method == "POST"
    assert request.headers["x-goog-api-key"] == GOOGLE_TEST_KEY
    assert request.headers["x-goog-fieldmask"] == "places.displayName,places.formattedAddress,places.location,places.rating,places.primaryType"
    assert request.body == {"textQuery": "padaria perto de Paulista", "languageCode": "pt-BR", "maxResultCount": 8}
    assert result["results"] == [{"name": "Padaria Google", "address": "Av. Paulista, 1000", "lat": -23.56, "lon": -46.65, "category": "bakery", "rating": 4.6}]
    assert GOOGLE_TEST_KEY not in json.dumps(result)


def test_google_key_saved_in_settings_is_used(net, monkeypatch):
    # set_api_keys também grava no ambiente: o monkeypatch devolve o ambiente como estava.
    monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
    monkeypatch.setenv("GOOGLE_PLACES_API_KEYS", "")
    runtime_settings.set_api_keys({"google_places": GOOGLE_TEST_KEY})
    assert runtime_settings.get_api_keys()["google_places"] == GOOGLE_TEST_KEY
    assert places.search_places("padaria")["provider"] == "google"


def test_google_failure_falls_back_to_osm_and_says_so(net, monkeypatch):
    monkeypatch.setenv("GOOGLE_PLACES_API_KEYS", GOOGLE_TEST_KEY)
    net.fail_google = urllib.error.HTTPError(places.GOOGLE_TEXT_SEARCH_URL, 403, "Forbidden", {}, None)
    result = places.search_places("padaria")
    assert result["ok"] is True and result["provider"] == "osm"
    assert "Google Places falhou" in result["notice"] and "OpenStreetMap" in result["notice"]
    assert [request.url.split("?")[0] for request in net.requests] == [places.GOOGLE_TEXT_SEARCH_URL, places.NOMINATIM_URL]
    assert GOOGLE_TEST_KEY not in json.dumps(result)
    tool = PlacesSearchTool().execute({"query": "padaria"})
    assert tool.ok is True and tool.message.startswith("O Google Places falhou")


def test_network_error_is_not_ok(net):
    net.fail_osm = urllib.error.URLError(OSError("sem rede"))
    result = places.search_places("padaria")
    assert result["ok"] is False and "Não foi possível buscar lugares" in result["error"]
    assert "results" not in result
    assert places.cached_search("padaria") is None
    tool = PlacesSearchTool().execute({"query": "padaria"})
    assert tool.ok is False and "Não foi possível buscar lugares" in tool.message


def test_invalid_query_is_refused_without_network(net):
    assert places.search_places("")["ok"] is False
    assert places.search_places("x" * 121)["ok"] is False
    assert places.search_places("padaria", "y" * 81)["ok"] is False
    assert net.requests == []


def test_empty_result_is_ok_and_says_nothing_found(net):
    net.osm = []
    tool = PlacesSearchTool().execute({"query": "lugar inexistente"})
    assert tool.ok is True and tool.data["results"] == [] and "Nenhum lugar encontrado" in tool.message


def test_tool_is_observe_general_and_routed_for_groq():
    metadata = TOOL_CATALOG["places_search"]
    assert metadata.default_risk == "observe" and not metadata.requires_confirmation
    assert "OpenStreetMap" in metadata.scope and "Google" in metadata.scope
    assert "places_search" in GENERAL_TOOL_NAMES
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {"places_search": PlacesSearchTool()}
    assert registry.get_tool_metadata("places_search").default_risk == "observe"
    from app.agent.tools.lifestyle_tools import normalize_name
    text = normalize_name("Tem alguma padaria perto do trabalho?")
    assert any("places_search" in tools for pattern, tools in GROQ_KEYWORD_TOOLS if pattern.search(text))


def _route_registry(monkeypatch):
    registry = ToolRegistry.__new__(ToolRegistry)
    registry.tools = {"places_search": PlacesSearchTool()}
    monkeypatch.setattr("app.agent.tools.registry.registry", registry)


def test_get_places_route_runs_through_kernel_with_window_origin(net, monkeypatch):
    _route_registry(monkeypatch)
    status, body = places_api.handle_places_get(["api", "places"], SimpleNamespace(path="/api/places?q=padaria&near=Bela%20Vista"))
    assert status == 200 and body["ok"] is True and body["provider"] == "osm"
    assert len(body["results"]) == 2 and body["bbox"]
    action = net.store.get(body["action"]["id"])
    assert action.tool_name == "places_search" and action.status == "succeeded" and action.risk == "observe"
    details = net.store.run_details(action.run_id)
    assert details["run"]["origin"] == "window"
    # Rota de janela não gera popup.
    assert ui_events.current_popups.get() is None


def test_get_places_route_errors(net, monkeypatch):
    _route_registry(monkeypatch)
    status, body = places_api.handle_places_get(["api", "places"], SimpleNamespace(path="/api/places?q="))
    assert status == 400 and body["ok"] is False
    net.fail_osm = urllib.error.URLError(OSError("sem rede"))
    status, body = places_api.handle_places_get(["api", "places"], SimpleNamespace(path="/api/places?q=padaria"))
    assert status == 502 and body["ok"] is False and "Não foi possível buscar lugares" in body["error"]
    assert places_api.handle_places_get(["api", "placesx"], SimpleNamespace(path="/api/placesx")) is None


def test_places_popup_is_automatic_in_chat_turn(net):
    result = PlacesSearchTool().execute({"query": "padaria", "near": "Bela Vista"})
    collector = []
    token_popups = ui_events.current_popups.set(collector)
    token_origin = current_origin.set("chat")
    try:
        emitted = popups.after_tool_success("places_search", {"query": "padaria", "near": "Bela Vista"}, result)
    finally:
        ui_events.current_popups.reset(token_popups)
        current_origin.reset(token_origin)
    assert [popup["template"] for popup in emitted] == ["places"] and collector == emitted
    popup = emitted[0]
    assert popup["key"] == f"places:{places.search_key('padaria', 'Bela Vista')}"
    assert popup["data"]["provider"] == "osm" and popup["data"]["query"] == "padaria"
    assert [item["id"] for item in popup["data"]["results"]] == ["p0", "p1"]
    assert popup["animate"] == {"added_ids": ["p0", "p1"]}
    assert popup["data"]["attribution"] == "© colaboradores do OpenStreetMap"
    # O popup lê do cache: nenhuma requisição além da busca da ferramenta.
    assert len(net.requests) == 1


def test_places_popup_never_triggers_a_new_search(net):
    status, body = popups_api.handle_popups_get(["api", "popups", "places"], SimpleNamespace(path="/api/popups/places?query=padaria"))
    assert status == 400 and "Busque o lugar primeiro" in body["error"]
    assert net.requests == []
    places.search_places("padaria")
    status, body = popups_api.handle_popups_get(["api", "popups", "places"], SimpleNamespace(path="/api/popups/places?query=padaria"))
    assert status == 200 and body["popup"]["template"] == "places" and len(body["popup"]["data"]["results"]) == 2
    assert len(net.requests) == 1
