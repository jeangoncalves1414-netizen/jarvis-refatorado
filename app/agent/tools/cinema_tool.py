"""Ferramenta de busca de filmes e séries no Jarvis Cinema."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.cinema import CinemaService
from app.services.cinema_discovery import CinemaDiscoveryService


class CinemaTool(BaseTool):
    @property
    def name(self) -> str:
        return "cinema"

    @property
    def description(self) -> str:
        return (
            "Busca filmes e séries de TV e abre o Jarvis Cinema com trailer e links de disponibilidade legal. "
            "Use quando o usuário pedir informações, trailer ou onde assistir a um título."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "play", "discover", "detect_url"],
                    "description": (
                        "Ação a realizar: 'search' (buscar lista de filmes/séries) ou "
                        "'play' (abrir a ficha do título), 'discover' (pesquisar fontes aprovadas) ou "
                        "'detect_url' (analisar uma página escolhida pelo usuário)."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "Nome do filme ou série a buscar/reproduzir (ex: 'Matrix', 'Breaking Bad', 'Deadpool').",
                },
                "imdb_id": {
                    "type": "string",
                    "description": "ID do IMDb do filme/série (ex: 'tt0133093') se já conhecido.",
                },
                "url": {
                    "type": "string",
                    "description": "URL pública de uma página que o usuário quer analisar para detectar mídia exposta normalmente.",
                },
                "scope": {
                    "type": "string", "enum": ["approved", "web"],
                    "description": "Em discover: approved consulta fontes de cinema; web pesquisa sites em toda a web.",
                },
                "source": {
                    "type": "string",
                    "description": "Filtro opcional em discover: animesonlinecc, flixlat, 123pelicula, archive, youtube, plex, pluto ou domain:dominio.com. Por padrão pesquisa toda a web, excluindo Netflix e Amazon.",
                },
                "media_type": {
                    "type": "string",
                    "enum": ["auto", "movie", "tv"],
                    "description": "Tipo de mídia: 'movie' para filme, 'tv' para série de TV ou 'auto'.",
                },
                "season": {
                    "type": "integer",
                    "description": "Número da temporada (padrão: 1, apenas para séries).",
                },
                "episode": {
                    "type": "integer",
                    "description": "Número do episódio (padrão: 1, apenas para séries).",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")
        if not action:
            return ToolResult(ok=False, message="Ação é obrigatória.")

        query = str(args.get("query", "") or "").strip()
        imdb_id = str(args.get("imdb_id", "") or "").strip()
        url = str(args.get("url", "") or "").strip()
        media_type = str(args.get("media_type", "auto") or "auto").strip()
        season = int(args.get("season", 1) or 1)
        episode = int(args.get("episode", 1) or 1)

        if action == "search":
            if not query:
                return ToolResult(ok=False, message="Informe o nome do filme ou série para buscar.")
            res = CinemaService.search_media(query, media_type=media_type)
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Nenhum resultado encontrado."))

            items = res.get("results", [])
            lines = [f"Resultados encontrados para '{query}':" if items else f"Nenhum título encontrado para '{query}'. Tente pesquisar sites com discover."]
            for idx, item in enumerate(items, 1):
                type_label = "Filme" if item["type"] == "movie" else "Série"
                lines.append(f"{idx}. {item['title']} ({item['year']}) [{type_label}] - ID: {item['id']}")

            payload = {"ok": True, "title": query, "type": "movie", "catalog_results": items}
            import json as _json
            return ToolResult(
                ok=True,
                message="\n".join(lines) + f"\n__CINEMA_PLAY__{_json.dumps(payload, ensure_ascii=False)}",
                data=payload,
            )

        if action == "discover":
            if not query:
                return ToolResult(ok=False, message="Informe o título para pesquisar nas fontes aprovadas.")
            scope = str(args.get("scope") or "web")
            source_id = str(args.get("source") or "")
            res = CinemaDiscoveryService().search(query, scope=scope, source_id=source_id)
            if not res.get("ok"):
                return ToolResult(ok=False, message=res.get("error", "Não foi possível pesquisar fontes."))
            payload = {"ok": True, "title": query, "type": "movie", "scope": scope, "source_id": source_id,
                       "discovery_results": res.get("results", []), "warnings": res.get("warnings", [])}
            import json as _json
            return ToolResult(
                ok=True,
                message=f"Pesquisa de páginas para **{query}**: {len(payload['discovery_results'])} resultados. A disponibilidade de vídeo ainda não foi verificada.\n__CINEMA_PLAY__{_json.dumps(payload, ensure_ascii=False)}",
                data=payload,
            )

        if action == "detect_url":
            if not url:
                return ToolResult(ok=False, message="Informe a URL que deseja analisar.")
            payload = {"ok": True, "title": query or "Mídia detectada", "type": "movie", "detect_url": url}
            import json as _json
            return ToolResult(
                ok=True,
                message=f"Analisando a página escolhida.\n__CINEMA_PLAY__{_json.dumps(payload, ensure_ascii=False)}",
                data=payload,
            )

        elif action == "play":
            target_item = None
            if imdb_id:
                target_item = {"id": imdb_id, "title": query or imdb_id, "type": media_type, "poster": ""}
            elif query:
                search_res = CinemaService.search_media(query, media_type=media_type)
                if search_res.get("ok") and search_res.get("results"):
                    target_item = search_res["results"][0]

            if not target_item:
                return ToolResult(ok=False, message=f"Não foi possível encontrar '{query}' para reproduzir.")

            # Validação extra: garantir que exista um IMDb ID válido (tt1234567)
            import re
            tid = str(target_item.get("id") or "").strip()
            if not re.match(r'^tt\d{6,}$', tid):
                return ToolResult(ok=False, message=f"ID inválido para reprodução: '{tid}'. Por favor, informe o título ou o ID do IMDb.")

            player_data = CinemaService.get_player_data(
                imdb_id=target_item["id"],
                media_type=target_item.get("type", media_type),
                title=target_item.get("title", query),
                poster=target_item.get("poster", ""),
                season=season,
                episode=episode,
            )

            if not player_data.get("ok"):
                return ToolResult(ok=False, message=player_data.get("error", "Não foi possível preparar o título."))

            try:
                discovery = CinemaDiscoveryService().search(player_data.get("title", query), limit=8)
                player_data["discovery_results"] = discovery.get("results", []) if discovery.get("ok") else []
            except Exception:
                player_data["discovery_results"] = []

            # Resposta formatada para acionar a reprodução na UI via marcador __CINEMA_PLAY__
            import json as _json
            type_str = "Série" if player_data["type"] == "tv" else "Filme"
            ep_str = f" (T{season}:E{episode})" if player_data["type"] == "tv" else ""
            msg = (
                f"🎬 Abrindo **{player_data['title']}**{ep_str} no Jarvis Cinema.\n"
                f"__CINEMA_PLAY__{_json.dumps(player_data, ensure_ascii=False)}"
            )
            return ToolResult(ok=True, message=msg, data=player_data)

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
