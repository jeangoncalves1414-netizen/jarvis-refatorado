"""GET /api/popups/<template>: monta um popup sem IA para os comandos "/" e a paleta (lote 6).

Só leitura e sem Run (mesma regra C12 das leituras de janela). Os parâmetros vêm da query
string e passam pela mesma validação da ferramenta show_popup.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

from app.agent.popups import POPUP_TEMPLATES, build_popup


def _query_params(handler: Any, template: str) -> dict[str, Any]:
    raw = parse_qs(urlsplit(getattr(handler, "path", "") or "").query, keep_blank_values=False)
    spec = POPUP_TEMPLATES.get(template)
    list_params = spec.list_params if spec else frozenset()
    params: dict[str, Any] = {}
    for name, values in raw.items():
        params[name] = list(values) if name in list_params else values[-1]
    return params


def handle_popups_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) != 3 or parts[:2] != ["api", "popups"]:
        return None
    template = parts[2]
    try:
        popup = build_popup(template, _query_params(handler, template), origin="command")
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - serviço de dados fora do ar
        return 500, {"ok": False, "error": f"Não foi possível montar o popup ({type(exc).__name__})."}
    return 200, {"ok": True, "popup": popup}
