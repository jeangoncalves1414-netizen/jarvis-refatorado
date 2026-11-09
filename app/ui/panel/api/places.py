"""GET /api/places?q=&near=: busca de lugares da janela Lugares, sem IA (lote 6, Fase 5).

É uma consulta a terceiros (OpenStreetMap ou Google), então passa pelo Action Kernel com
``run_action("places_search", ..., origin="window")`` e aparece na Central. A janela só chama
esta rota quando a usuária envia a busca (sem autocompletar).
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.services.places import validate_search


def handle_places_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if parts != ["api", "places"]:
        return None
    raw = parse_qs(urlsplit(getattr(handler, "path", "") or "").query)
    query = (raw.get("q") or [""])[-1]
    near = (raw.get("near") or [""])[-1]
    try:
        query, near = validate_search(query, near)
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}

    from app.agent.action_gateway import run_action

    arguments: dict[str, Any] = {"query": query}
    if near:
        arguments["near"] = near
    outcome = run_action(
        "places_search", arguments, source="window:places",
        user_text=f"Buscar lugares: {query}" + (f" perto de {near}" if near else ""), origin="window",
    )
    action = outcome.action.public_dict() if outcome.action else None
    data = outcome.result.data if outcome.result else {}
    if outcome.succeeded:
        return 200, {
            "ok": True,
            "query": data.get("query", query),
            "near": data.get("near", near),
            "provider": data.get("provider", "osm"),
            "results": data.get("results") or [],
            "bbox": data.get("bbox"),
            "attribution": data.get("attribution") or "",
            "notice": data.get("notice") or "",
            "action": action,
        }
    if outcome.pending:
        return 202, {"ok": False, "pending": True, "error": "A busca aguarda aprovação na Central.", "action": action}
    message = outcome.result.message if outcome.result and outcome.result.message else "Não foi possível buscar lugares."
    return 502, {"ok": False, "error": message, "action": action}
