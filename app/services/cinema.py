"""Busca de filmes/séries e links para fontes legais no Jarvis Cinema."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
import time
from functools import lru_cache
from typing import Any


class CinemaService:
    """Busca metadados e cria atalhos para trailer e disponibilidade legal."""

    _STREMIO_BASE = "https://v3-cinemeta.strem.io"
    _LOCALIZED_BASE = "https://tmdb.elfhosted.com/pt-BR"

    @staticmethod
    @lru_cache(maxsize=128)
    def _catalog(url: str, hour: int) -> list[dict[str, Any]]:
        request = urllib.request.Request(url, headers={"User-Agent": "JarvisCinema/1.0", "Accept-Language": "pt-BR,pt;q=0.9"})
        with urllib.request.urlopen(request, timeout=10) as response:
            data = json.loads(response.read(3_000_000).decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("metas"), list):
            raise ValueError("Resposta de catálogo inválida")
        return data["metas"]

    @classmethod
    def search_media(cls, query: str, media_type: str = "auto") -> dict[str, Any]:
        """
        Busca filmes ou séries por título.
        media_type: 'movie', 'series' ou 'auto'.
        """
        clean_q = query.strip()
        if not clean_q:
            return {"ok": False, "error": "Query vazia."}
        media_type = {"tv": "series"}.get(media_type, media_type)
        if media_type not in {"auto", "movie", "series"}:
            return {"ok": False, "error": "Tipo de pesquisa inválido."}

        results = []
        failures = []
        warnings = []
        types_to_search = ["movie", "series"] if media_type == "auto" else [media_type]

        for mtype in types_to_search:
            try:
                encoded = urllib.parse.quote(clean_q[:160], safe="")
                localized = True
                try:
                    metas = cls._catalog(f"{cls._LOCALIZED_BASE}/catalog/{mtype}/tmdb.search/search={encoded}.json", int(time.time() // 3600))
                except Exception:
                    localized = False
                    metas = cls._catalog(f"{cls._STREMIO_BASE}/catalog/{mtype}/top/search={encoded}.json", int(time.time() // 3600))
                    warnings.append("Catálogo em português indisponível; alguns títulos estão no idioma original.")
                for item in metas[:20]:
                    if not isinstance(item, dict) or not item.get("name") or not (item.get("id") or item.get("imdb_id")):
                        continue
                    results.append({
                        "id": item.get("imdb_id") or item.get("id"),
                        "title": item.get("name"),
                        "title_language": "pt-BR" if localized else "original",
                        "type": "movie" if mtype == "movie" else "tv",
                        "year": item.get("releaseInfo") or item.get("year", "N/A"),
                        "poster": item.get("poster"),
                        "description": item.get("description", "Sem sinopse disponível."),
                        "genres": item.get("genres", []),
                    })
            except Exception as exc:
                failures.append(mtype)
                print(f"[CinemaService] Falha ao buscar {mtype} para '{clean_q}': {exc}")

        if not results and failures:
            return {"ok": False, "error": "O catálogo está indisponível agora. Tente a aba Sites ou pesquise novamente."}

        return {"ok": True, "query": clean_q, "total": len(results), "results": results, "partial": bool(failures), "warnings": list(dict.fromkeys(warnings))}

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
