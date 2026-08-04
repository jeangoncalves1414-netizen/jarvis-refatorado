"""Busca de filmes/séries e links para fontes legais no Jarvis Cinema."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Any


class CinemaService:
    """Busca metadados e cria atalhos para trailer e disponibilidade legal."""

    _STREMIO_BASE = "https://v3-cinemeta.strem.io"

    @classmethod
    def search_media(cls, query: str, media_type: str = "auto") -> dict[str, Any]:
        """
        Busca filmes ou séries por título.
        media_type: 'movie', 'series' ou 'auto'.
        """
        clean_q = query.strip()
        if not clean_q:
            return {"ok": False, "error": "Query vazia."}

        results = []
        types_to_search = ["movie", "series"] if media_type == "auto" else [media_type]

        for mtype in types_to_search:
            try:
                encoded = urllib.parse.quote(clean_q)
                url = f"{cls._STREMIO_BASE}/catalog/{mtype}/top/search={encoded}.json"
                req = urllib.request.Request(
                    url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=6) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                metas = data.get("metas", [])
                for item in metas[:5]:
                    results.append({
                        "id": item.get("id"),  # IMDb ID (ex: tt0133093)
                        "title": item.get("name"),
                        "type": "movie" if mtype == "movie" else "tv",
                        "year": item.get("releaseInfo") or item.get("year", "N/A"),
                        "poster": item.get("poster"),
                        "description": item.get("description", "Sem sinopse disponível."),
                        "genres": item.get("genres", []),
                    })
            except Exception as exc:
                print(f"[CinemaService] Falha ao buscar {mtype} para '{clean_q}': {exc}")

        if not results:
            return {"ok": False, "error": f"Nenhum filme ou série encontrado para '{query}'."}

        return {"ok": True, "query": clean_q, "total": len(results), "results": results}

    @classmethod
    def get_player_data(
        cls,
        imdb_id: str,
        media_type: str = "movie",
        title: str = "",
        poster: str = "",
        season: int = 1,
        episode: int = 1,
    ) -> dict[str, Any]:
        """Gera dados para apresentar o título em vez de incorporar streams de terceiros."""
        clean_id = imdb_id.strip()
        if not clean_id.startswith("tt") or not clean_id[2:].isdigit():
            return {"ok": False, "error": "ID do IMDb inválido."}

        is_tv = media_type.lower() in ("tv", "series")
        clean_title = title.strip() or clean_id
        query = urllib.parse.quote_plus(f"{clean_title} trailer oficial")
        watch_query = urllib.parse.quote_plus(clean_title)

        return {
            "ok": True,
            "imdb_id": clean_id,
            "title": clean_title,
            "type": "tv" if is_tv else "movie",
            "poster": poster,
            "season": season,
            "episode": episode,
            "trailer_url": f"https://www.youtube.com/results?search_query={query}",
            "watch_url": f"https://www.justwatch.com/br/busca?q={watch_query}",
            "imdb_url": f"https://www.imdb.com/title/{clean_id}/",
        }
