from __future__ import annotations

import io
import json
import urllib.request

import pytest

from app.agent.tools.cinema_tool import CinemaTool
from app.services.cinema import CinemaService
from app.services.cinema_discovery import CinemaDiscoveryService, _PublicRedirectHandler


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    CinemaService._catalog.cache_clear()
    yield
    CinemaService._catalog.cache_clear()


@pytest.fixture
def discovery(tmp_path, monkeypatch):
    service = CinemaDiscoveryService(tmp_path / "sources.json")
    monkeypatch.setattr(service, "_search_internet_archive", lambda *args: [])
    monkeypatch.setattr(service, "_search_native", lambda *args: [])
    return service


def row(url, title="Matrix"):
    return {"url": url, "title": title, "snippet": "Descrição"}


def test_source_filter_applies_to_returned_links_and_unwraps_redirects(discovery, monkeypatch):
    calls = []
    def lookup(query, domains, limit):
        calls.append(domains)
        return [row("https://plex.tv.evil.test/title/1"), row("https://unrelated.example/movie"),
                row("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.plex.tv%2Ftitle%2F1%3Futm_source%3Dddg"),
                row("https://www.plex.tv/title/1#details")]
    monkeypatch.setattr(discovery, "_search_web", lookup)
    result = discovery.search("Matrix", source_id="plex")
    assert calls == [["plex.tv"]]
    assert [r["url"] for r in result["results"]] == ["https://www.plex.tv/title/1"]
    assert result["results"][0]["source"] == "plex.tv"


def test_web_scope_can_find_other_sites_but_not_unsafe_links(discovery, monkeypatch):
    def lookup(query, domains, limit):
        assert domains == []
        return [row("javascript:alert(1)"), row("file:///secret"), row("http://127.0.0.1/"),
                row("https://user:pass@example.com/"), row("https://docs.python.org/3/")]
    monkeypatch.setattr(discovery, "_search_web", lookup)
    assert [r["url"] for r in discovery.search("Python", scope="web")["results"]] == ["https://docs.python.org/3/"]


def test_archive_does_not_starve_web_results(discovery, monkeypatch):
    monkeypatch.setattr(discovery, "_search_internet_archive", lambda *a: [row(f"https://archive.org/details/{i}") for i in range(12)])
    monkeypatch.setattr(discovery, "_search_web", lambda *a: [row("https://www.plex.tv/movie/matrix")])
    results = discovery.search("Matrix", limit=3, scope="approved")["results"]
    assert len(results) == 3
    assert results[0]["source"] == "plex.tv"
    assert results[1]["source"] == "archive.org"


def test_web_preserves_provider_order_without_registered_source_boost(discovery, monkeypatch):
    monkeypatch.setattr(discovery, "_search_web", lambda *a: [
        row("https://example.org/matrix", "Matrix em uma página comum"),
        row("https://www.plex.tv/movie/matrix", "Matrix no Plex"),
        row("https://archive.org/details/matrix", "Matrix no Archive"),
    ])
    results = discovery.search("Matrix", scope="web")["results"]
    assert [item["source"] for item in results] == ["example.org", "plex.tv", "archive.org"]
    assert [item["source_priority"] for item in results] == [100, 10, 40]


@pytest.mark.parametrize('query,expected', [
    ('It: A Coisa 2017', 'Assistir It: A Coisa 2017 completo dublado'),
    ('Assistir It: A Coisa 2017 completo dublado', 'Assistir It: A Coisa 2017 completo dublado'),
    ('It: A Coisa 2017 legendado', 'Assistir It: A Coisa 2017 legendado completo'),
    ('It: A Coisa trailer', 'It: A Coisa trailer'),
])
def test_watch_query_respects_existing_intent(query, expected):
    from app.services.cinema_discovery import _watch_query
    assert _watch_query(query) == expected


def test_watch_ranking_precedes_limit_without_blocking_youtube_or_news(discovery, monkeypatch):
    rows = [row('https://www.youtube.com/watch?v=trailer', 'It A Coisa 2017 trailer dublado'),
            row('https://g1.globo.com/cinema/it', 'It A Coisa 2017: crítica'),
            row('https://cinema.example.to/it', 'Assistir It A Coisa 2017 completo dublado')]
    monkeypatch.setattr(discovery, '_search_web', lambda *a: rows)
    results = discovery.search('It A Coisa 2017', limit=1)['results']
    assert results[0]['url'] == rows[2]['url']
    assert len(discovery.search('It A Coisa 2017')['results']) == 3


def test_watch_query_reaches_first_and_later_search_pages(monkeypatch):
    from app.agent.tools import web_search
    import ddgs
    calls = []
    def search(query, *args, **kwargs):
        calls.append(query)
        return [row('https://example.to/it', 'It A Coisa 2017')]
    monkeypatch.setattr(web_search, '_search', search)
    monkeypatch.setattr(web_search, '_fallback_search', search)
    class Provider:
        def __init__(self, **kwargs):
            pass
        def text(self, query, **kwargs):
            return search(query)
    monkeypatch.setattr(ddgs, 'DDGS', Provider)
    for page in (1, 2):
        assert CinemaDiscoveryService._search_web('It A Coisa 2017', [], 1, page=page)
    assert calls == ['Assistir It A Coisa 2017 completo dublado'] * 3


def test_invalid_filter_does_not_run_search(discovery, monkeypatch):
    monkeypatch.setattr(discovery, "_search_web", lambda *a: pytest.fail("Search should not run"))
    assert not discovery.search("x", source_id="unknown")["ok"]
    assert not discovery.search("x", scope="unknown")["ok"]
    assert not discovery.search(" ")["ok"]


def test_failure_is_distinct_from_no_results(discovery, monkeypatch):
    def fail(*args):
        raise TimeoutError()
    monkeypatch.setattr(discovery, "_search_web", fail)
    assert not discovery.search("Matrix", scope="web")["ok"]
    monkeypatch.setattr(discovery, "_search_internet_archive", lambda *a: [row("https://archive.org/details/test")])
    partial = discovery.search("Matrix", scope="approved")
    assert partial["ok"] and partial["warnings"] and partial["results"]
    monkeypatch.setattr(discovery, "_search_web", lambda *a: [])
    assert discovery.search("Matrix", scope="web")["ok"]


def test_search_query_scopes_provider_and_falls_back_on_empty(monkeypatch):
    from app.agent.tools import web_search
    calls = []
    monkeypatch.setattr(web_search, "_search", lambda query, limit: calls.append(query) or [])
    monkeypatch.setattr(web_search, "_fallback_search", lambda query, limit: calls.append(query) or [row("https://plex.tv/movie")])
    assert CinemaDiscoveryService._search_web("Matrix", ["plex.tv", "pluto.tv"], 5)
    assert calls == ["Matrix (site:plex.tv OR site:pluto.tv)"] * 2


def test_search_rejects_provider_results_unrelated_to_the_title(monkeypatch):
    from app.agent.tools import web_search
    monkeypatch.setattr(web_search, '_search', lambda *args: [row('https://example.org/o', 'Aprenda a letra O')])
    monkeypatch.setattr(web_search, '_fallback_search', lambda *args: [row('https://example.org/terminator', 'O Exterminador do Futuro (1984)'), row('https://example.org/music', 'Show de música')])
    result = CinemaDiscoveryService._search_web('O Exterminador do Futuro 1984 assistir online grátis', [], 8)
    assert [item['url'] for item in result] == ['https://example.org/terminator']


def test_unrelated_search_tries_independent_html_provider(monkeypatch):
    from app.agent.tools import web_search
    monkeypatch.setattr(web_search, '_search', lambda *args: [row('https://example.org/other', 'Outro título')])
    monkeypatch.setattr(web_search, '_fallback_search', lambda *args: [])
    html = b'<a class="result__a" href="https://example.org/matrix">Matrix</a><a class="result__snippet">Filme completo</a>'
    monkeypatch.setattr(urllib.request, 'urlopen', lambda *args, **kwargs: io.BytesIO(html))
    assert CinemaDiscoveryService._search_web('Matrix assistir online', [], 8)[0]['title'] == 'Matrix'


def test_series_alias_and_query_path_are_encoded(monkeypatch):
    urls = []
    def request(req, **kwargs):
        urls.append(req.full_url)
        return io.BytesIO(json.dumps({"metas": [{"id": "tt1234567", "name": "Série", "year": 2020}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", request)
    result = CinemaService.search_media("A/B & C", "tv")
    assert "/pt-BR/catalog/series/tmdb.search/search=A%2FB%20%26%20C.json" in urls[0]
    assert result["results"][0]["type"] == "tv"
    assert not CinemaService.search_media("x", "invalid")["ok"]


def test_catalog_no_results_is_not_a_network_failure(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: io.BytesIO(b'{"metas": []}'))
    assert CinemaService.search_media("not found")["ok"]
    def fail(*args, **kwargs):
        raise TimeoutError()
    monkeypatch.setattr(urllib.request, "urlopen", fail)
    result = CinemaService.search_media("Matrix")
    assert not result["ok"] and "indisponível" in result["error"]


def test_agent_propagates_scope_and_source(monkeypatch):
    calls = []
    monkeypatch.setattr(CinemaDiscoveryService, "search", lambda self, query, **kw: calls.append(kw) or {"ok": True, "results": [row("https://example.com/")]})
    result = CinemaTool().execute({"action": "discover", "query": "filmes", "scope": "web", "source": "plex"})
    assert result.ok and result.data["scope"] == "web" and result.data["source_id"] == "plex"
    assert calls == [{"scope": "web", "source_id": "plex"}]
    assert "__CINEMA_PLAY__" in result.message


def test_redirect_to_local_network_is_rejected(monkeypatch):
    monkeypatch.setattr(CinemaDiscoveryService, "_is_public_http_url", lambda url: not url.startswith("http://127."))
    with pytest.raises(ValueError, match="não público"):
        _PublicRedirectHandler().redirect_request(urllib.request.Request("https://example.com"), None, 302, "Found", {}, "http://127.0.0.1/secret")


@pytest.mark.parametrize("url", ["http://[bad", "file:///video.mp4", "http://localhost/video.mp4", "https://u:p@example.org/x"])
def test_probe_rejects_invalid_urls_without_fetching(discovery, url):
    assert discovery.probe(url)["ok"] is False


def test_paged_search_queries_provider_page_and_stops_when_empty(discovery, monkeypatch):
    import ddgs
    calls = []
    class Provider:
        def __init__(self, **kwargs):
            pass
        def text(self, query, **kwargs):
            calls.append((query, kwargs))
            return [{"title": "Matrix", "href": "https://example.org/matrix"}] if kwargs["page"] == 2 else []
    monkeypatch.setattr(ddgs, "DDGS", Provider)
    result = discovery.search("Matrix", limit=24, page=2)
    assert result["next_page"] == 3
    assert result["results"][0]["url"] == "https://example.org/matrix"
    assert calls == [("Assistir Matrix completo dublado", {"max_results": 24, "page": 2})]
    assert discovery.search("Matrix", limit=24, page=3)["next_page"] is None
    assert not discovery.search("Matrix", page="invalid")["ok"]
    assert not discovery.search("Matrix", page=101)["ok"]


def test_search_routes_forward_filters(tmp_path, monkeypatch):
    from app.ui.panel.server import PanelHandler
    calls = []
    monkeypatch.setattr(CinemaDiscoveryService, "search", lambda self, query, **kw: calls.append((query, kw)) or {"ok": True, "results": []})
    handler = object.__new__(PanelHandler)
    handler.path = "/api/cinema/discovery/search?q=Matrix&scope=web&source=plex"
    handler.headers = {}
    handler._authorize_api = lambda *args: {"kind": "local"}
    sent = []
    handler._send_json = lambda status, data: sent.append((status, data))
    handler.do_GET()
    assert calls == [("Matrix", {"scope": "web", "source_id": "plex"})]
    assert sent[0][0] == 200
    handler.path = "/api/cinema/discovery/search?q=Matrix&scope=web&page=2&limit=24"
    handler.do_GET()
    assert calls[-1] == ("Matrix", {"scope": "web", "source_id": "", "page": "2", "limit": "24"})
    monkeypatch.setattr(CinemaDiscoveryService, "_sources", lambda self: [{"id": "plex", "name": "Plex"}])
    handler.path = "/api/cinema/discovery/sources"
    handler.do_GET()
    assert sent[-1][1]["sources"][0]["id"] == "plex"


def test_paid_sites_are_excluded_even_from_existing_configuration(discovery, monkeypatch):
    discovery.sources_path.write_text(json.dumps({"sources": [
        {"id": "netflix", "domains": ["netflix.com"]}, {"id": "primevideo", "domains": ["amazon.com"]},
        {"id": "custom", "domains": ["example.org"]},
    ]}))
    monkeypatch.setattr(discovery, "_search_web", lambda *args: [row("https://netflix.com/a"), row("https://www.amazon.com.br/a"), row("https://primevideo.com/b"), row("https://example.org/video")])
    result = discovery.search("filme")
    assert [item["source"] for item in result["results"]] == ["example.org"]
    assert not {"netflix", "primevideo"}.intersection(item["id"] for item in result["sources"])


def test_custom_domain_filter_and_validation(discovery, monkeypatch):
    calls = []
    monkeypatch.setattr(discovery, "_search_web", lambda q, domains, limit: calls.append(domains) or [row("https://animesonlinecc.to/anime/test"), row("https://elsewhere.example/video")])
    result = discovery.search("anime", source_id="domain:animesonlinecc.to")
    assert len(result["results"]) == 1 and calls == [["animesonlinecc.to"]]
    assert not discovery.search("anime", source_id="domain:localhost/secret")["ok"]


def test_localized_catalog_preserves_portuguese_title_and_imdb(monkeypatch):
    def request(req, **kwargs):
        assert "/pt-BR/" in req.full_url
        return io.BytesIO(json.dumps({"metas": [{"id": "tmdb:218", "imdb_id": "tt0088247", "name": "O Exterminador do Futuro", "description": "Um androide volta ao passado."}]}).encode())
    monkeypatch.setattr(urllib.request, "urlopen", request)
    item = CinemaService.search_media("O Exterminador do Futuro", "movie")["results"][0]
    assert item["id"] == "tt0088247" and item["title"] == "O Exterminador do Futuro" and item["title_language"] == "pt-BR"


def test_localized_catalog_failure_has_explicit_original_language_fallback(monkeypatch):
    def request(req, **kwargs):
        if "/pt-BR/" in req.full_url:
            raise TimeoutError()
        return io.BytesIO(b'{"metas": [{"id": "tt0088247", "name": "The Terminator"}]}')
    monkeypatch.setattr(urllib.request, "urlopen", request)
    result = CinemaService.search_media("Terminator", "movie")
    assert result["ok"] and result["warnings"] and result["results"][0]["title_language"] == "original"


def test_html_episodes_sources_and_labels_are_extracted_without_inventing_pagination():
    from app.services.cinema_page import parse_page
    result = parse_page('''<a href="?page=2">2</a><a href="/serie/s02e03">Episódio 3</a>
        <a href="/watch/four" data-season="2" data-episode="4">4</a>
        <video><source src="/video-720.mp4" label="720p Dublado"></video>
        <script type="application/ld+json">{"@type":"TVEpisode","episodeNumber":5,"partOfSeason":{"seasonNumber":2},"url":"/watch/5","name":"Final"}</script>''', "https://example.org/serie/")
    assert [(item["season"], item["episode"]) for item in result["episodes"]] == [(2, 3), (2, 4), (2, 5)]
    assert result["media"][0]["quality"] == "720p" and result["media"][0]["audio"] == "Dublado"
    assert result["media"][0]["url"] == "https://example.org/video-720.mp4"


def test_obvious_ad_endpoints_are_labeled_and_ranked_after_content():
    from app.services.cinema_page import is_probable_ad_media, media_info
    assert is_probable_ad_media('https://cdn.example/adserver/preroll.mp4')
    assert not is_probable_ad_media('https://cdn.example/video.mp4')
    assert media_info('https://cdn.example/ads/spot.mp4')['suspected_ad'] is True


def test_probe_does_not_treat_an_iframe_as_a_confirmed_video(discovery, monkeypatch):
    from app.services import cinema_page
    from email.message import Message
    response = io.BytesIO(b'<iframe src="https://player.example/watch"></iframe><a href="/s01e02">Episode 2</a>')
    response.geturl = lambda: "https://example.org/series"
    response.headers = Message()
    response.headers["Content-Type"] = "text/html"
    monkeypatch.setattr(discovery, "_is_public_http_url", lambda url: url.startswith("https://"))
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: type("Opener", (), {"open": lambda *a, **kw: response})())
    monkeypatch.setattr(cinema_page, "inspect_dynamic", lambda *args, **kwargs: {"media": [], "episodes": []})
    result = discovery.probe("https://example.org/series")
    assert result["media"][0]["direct"] is False
    assert not result["media"][0].get("compatible")
    assert result["episodes"][0]["episode"] == 2


def test_fast_probe_keeps_direct_html_media_without_opening_a_browser(discovery, monkeypatch):
    from app.services import cinema_page
    from email.message import Message
    response = io.BytesIO(b'<video><source src="https://cdn.example/video.mp4"></video>')
    response.geturl = lambda: "https://example.org/watch"
    response.headers = Message()
    response.headers["Content-Type"] = "text/html"
    monkeypatch.setattr(discovery, "_is_public_http_url", lambda url: url.startswith("https://"))
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: type("Opener", (), {"open": lambda *a, **kw: response})())
    monkeypatch.setattr(cinema_page, "inspect_dynamic", lambda *args, **kwargs: pytest.fail("browser should not be opened"))
    result = discovery.probe("https://example.org/watch", fast=True)
    assert result["media"][0]["url"] == "https://cdn.example/video.mp4"
