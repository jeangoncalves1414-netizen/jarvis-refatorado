"""Ferramenta de busca e reprodução de filmes e séries no Jarvis Cinema (Ad-Free Player)."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.cinema import CinemaService


class CinemaTool(BaseTool):
    @property
    def name(self) -> str:
        return "cinema"

    @property
    def description(self) -> str:
        return (
            "Busca e reproduz filmes e séries de TV em tempo real em um player futurista integrado livre de anúncios. "
            "Use quando o usuário pedir para assistir ou colocar um filme ou série de TV."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["search", "play"],
                    "description": (
                        "Ação a realizar: 'search' (buscar lista de filmes/séries) ou "
                        "'play' (abrir o player diretamente para reproduzir o título)."
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
            lines = [f"Resultados encontrados para '{query}':"]
            for idx, item in enumerate(items, 1):
                type_label = "Filme" if item["type"] == "movie" else "Série"
                lines.append(f"{idx}. {item['title']} ({item['year']}) [{type_label}] - ID: {item['id']}")

            return ToolResult(ok=True, message="\n".join(lines), data=res)

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

            # Garantir que exista uma URL de player válida antes de emitir o marcador
            default_url = str(player_data.get("default_url") or "").strip()
            if not default_url or not default_url.lower().startswith("http"):
                return ToolResult(ok=False, message="Não foi possível gerar um player válido para este título.")

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
