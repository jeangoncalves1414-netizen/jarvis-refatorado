from __future__ import annotations

from app.services.cinema import CinemaService
from app.services.climate_control import ClimateControlService
from app.services.cinema_library import CinemaLibraryService
from app.services.cinema_discovery import CinemaDiscoveryService
from app.agent.tools.cinema_tool import CinemaTool
from app.services.realtime import RealTimeService


def test_climate_target_is_validated_and_persisted(tmp_path) -> None:
    service = ClimateControlService(tmp_path / "climate.json")

    assert service.get_state()["target_c"] == 22
    assert service.set_target(24)["target_c"] == 24
    assert service.get_state()["target_c"] == 24
    assert service.set_target(31)["ok"] is False


def test_cinema_returns_legal_discovery_links() -> None:
    result = CinemaService.get_player_data("tt0133093", title="Matrix")

    assert result["ok"] is True
    assert result["trailer_url"].startswith("https://www.youtube.com/")
    assert result["watch_url"].startswith("https://www.justwatch.com/")
    assert "vidsrc" not in str(result).lower()


def test_cinema_library_keeps_episode_sources(tmp_path) -> None:
    service = CinemaLibraryService(tmp_path / "cinema_library.json")
    first = service.upsert_source({
        "title": "Minha Série",
        "type": "tv",
        "season": 1,
        "episode": 2,
        "label": "720p",
        "url": "https://media.example.com/episode-2.m3u8",
    })
    second = service.upsert_source({
        "title": "Minha Série",
        "type": "tv",
        "season": 1,
        "episode": 2,
        "label": "1080p",
        "url": "https://media.example.com/episode-2-1080.mp4",
    })

    assert first["ok"] is True
    assert second["ok"] is True
    item = service.list_items()["items"][0]
    assert item["episodes"][0]["episode"] == 2
    assert len(item["episodes"][0]["sources"]) == 2
    assert service.upsert_source({"title": "X", "url": "file:///video.mp4"})["ok"] is False


def test_cinema_discovery_filters_search_to_approved_sources(tmp_path, monkeypatch) -> None:
    service = CinemaDiscoveryService(tmp_path / "cinema_sources.json")
    monkeypatch.setattr(service, "_search_internet_archive", lambda *args: [])
    monkeypatch.setattr(service, "_search_web", lambda query, domains, limit: [
        {"title": "Arquivo público", "url": "https://archive.org/details/example", "source": "archive.org", "snippet": ""}
    ])

    result = service.search("filme de domínio público")

    assert result["ok"] is True
    assert result["results"][0]["source"] == "archive.org"


def test_cinema_discovery_returns_direct_media_without_fetching(monkeypatch, tmp_path) -> None:
    service = CinemaDiscoveryService(tmp_path / "cinema_sources.json")
    monkeypatch.setattr(service, "_is_public_http_url", lambda url: url.startswith("https://"))

    result = service.probe("https://media.example.com/video.m3u8")

    assert result["ok"] is True
    assert len(result["media"]) == 1
    media_item = result["media"][0]
    assert media_item["url"] == "https://media.example.com/video.m3u8"
    assert media_item["label"] == "URL direta"
    assert media_item["kind"] == "HLS"


def test_cinema_search_returns_modal_payload(monkeypatch) -> None:
    monkeypatch.setattr(CinemaService, "search_media", lambda *args, **kwargs: {
        "ok": True,
        "results": [{"id": "tt0133093", "title": "Matrix", "type": "movie", "year": "1999", "poster": ""}],
    })

    result = CinemaTool().execute({"action": "search", "query": "Matrix"})

    assert result.ok is True
    assert result.data["catalog_results"][0]["title"] == "Matrix"
    assert "__CINEMA_PLAY__" in result.message


def test_weather_uses_open_meteo_response(monkeypatch) -> None:
    responses = iter((
        {"results": [{"name": "Sertãozinho", "admin1": "São Paulo", "latitude": -21.14, "longitude": -48.0}]},
        {
            "current": {
                "temperature_2m": 23.0,
                "apparent_temperature": 24.0,
                "relative_humidity_2m": 60,
                "wind_speed_10m": 12.0,
                "weather_code": 2,
            },
            "daily": {"temperature_2m_max": [29.0], "temperature_2m_min": [17.0]},
        },
    ))
    monkeypatch.setattr(RealTimeService, "_get_json", lambda *args, **kwargs: next(responses))

    result = RealTimeService.get_weather("Sertaozinho")

    assert result["ok"] is True
    assert result["city"] == "Sertãozinho, São Paulo"
    assert result["description"] == "Parcialmente nublado"
