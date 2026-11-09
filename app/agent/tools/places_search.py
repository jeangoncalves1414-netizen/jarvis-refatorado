"""Ferramenta places_search: procura lugares e endereços (lote 6, Fase 5).

Usa ``app.services.places`` (OpenStreetMap por padrão; Google Places só com chave configurada).
Só lê: envia o texto da busca ao provedor de mapas e devolve os resultados normalizados.
O popup ``places`` aparece sozinho depois de uma busca que deu certo.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool
from app.services import places

_PROVIDER_LABEL = {"osm": "OpenStreetMap", "google": "Google Places"}
_LISTED_IN_MESSAGE = 5


class PlacesSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "places_search"

    @property
    def description(self) -> str:
        return (
            "Procura lugares, estabelecimentos e endereços no mapa (ex.: 'padaria perto da Avenida Paulista', "
            "'onde fica o Parque Ibirapuera'). Usa o OpenStreetMap (ou o Google Places, se houver chave). "
            "Devolve nome, endereço e coordenadas; um popup com a lista e o mapa aparece sozinho. "
            "Não use para pesquisa geral na internet (use web_search). Não altera nada."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": f"O que procurar (até {places.MAX_QUERY} caracteres): tipo de lugar, nome ou endereço."},
                "near": {"type": "string", "description": f"Opcional: bairro, cidade ou referência (até {places.MAX_NEAR} caracteres)."},
            },
            "required": ["query"],
        }

    def run(self, query: str = "", near: str = "", command: str = "", **kwargs: Any) -> dict[str, Any]:
        # O caminho de marcadores envia só um texto em "command".
        result = places.search_places(query or command, near)
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error") or "Não foi possível buscar lugares."}
        found = result.get("results") or []
        provider = _PROVIDER_LABEL.get(result.get("provider"), "OpenStreetMap")
        where = f" perto de {result['near']}" if result.get("near") else ""
        if not found:
            message = f"Nenhum lugar encontrado para '{result['query']}'{where} ({provider})."
        else:
            listed = "; ".join(
                f"{item['name']} — {item['address']}" if item.get("address") else item["name"]
                for item in found[:_LISTED_IN_MESSAGE]
            )
            message = f"{len(found)} lugar(es) para '{result['query']}'{where} ({provider}): {listed}."
        if result.get("notice"):
            message = f"{result['notice']} {message}"
        return {
            "ok": True,
            "message": message,
            "query": result["query"],
            "near": result.get("near", ""),
            "key": result.get("key"),
            "provider": result.get("provider"),
            "results": found,
            "bbox": result.get("bbox"),
            "attribution": result.get("attribution"),
            "notice": result.get("notice", ""),
        }
