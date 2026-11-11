"""Ferramenta open_window: pede ao painel que abra uma janela pronta do app.

O agente só escolhe um id do registro abaixo e preenche parâmetros validados.
Nunca gera interface nem código. O resultado segue pelo mesmo canal da resposta
do chat (``context.tool_results.open_window.data.ui_window``) e o painel valida
de novo o id e os parâmetros antes de abrir. O espelho no frontend está em
``frontend/src/windows/registry.ts``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from app.agent.tools.base import BaseTool

MAX_TEXT = 300


def _text(limit: int = MAX_TEXT) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("deve ser texto")
        cleaned = value.strip()
        if len(cleaned) > limit:
            raise ValueError(f"deve ter no máximo {limit} caracteres")
        return cleaned
    return check


def _choice(*options: str) -> Callable[[Any], str]:
    def check(value: Any) -> str:
        if not isinstance(value, str) or value.strip().lower() not in options:
            raise ValueError("deve ser um de: " + ", ".join(options))
        return value.strip().lower()
    return check


def _positive_number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 < value <= 1_000_000_000:
        raise ValueError("deve ser um número maior que zero")
    return float(value)


def _iso_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("deve ser uma data AAAA-MM-DD")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError("deve ser uma data AAAA-MM-DD") from None


@dataclass(frozen=True)
class WindowSpec:
    title: str
    params: dict[str, Callable[[Any], Any]]


# Janelas que o agente pode pedir. Cada nova janela do frontend entra aqui e em windows/registry.ts.
WINDOWS: dict[str, WindowSpec] = {
    "home": WindowSpec("Casa", {}),
    # Só abre o painel; brilho, bloqueio e volume são acionados pelo usuário na própria janela.
    "pc-controls": WindowSpec("Controles do PC", {}),
    "finance": WindowSpec(
        "Finanças",
        {
            "type": _choice("expense", "income"),
            "category": _text(60),
            "edit_id": _text(64),
            "period": _choice("week", "month", "all"),
            "amount": _positive_number,
            "description": _text(),
            "date": _iso_date,
        },
    ),
    # Busca de lugares com mapa: query/near só preenchem o campo e disparam a busca na janela.
    "places": WindowSpec("Lugares", {"query": _text(120), "near": _text(80)}),
    # Lista e editor de rotinas; routine_id só seleciona uma rotina ao abrir.
    "routines": WindowSpec("Rotinas", {"routine_id": _text(60)}),
    # Painel Life OS: Checklists Inteligentes e Hábitos Modulares
    "life-os": WindowSpec("Life OS", {"tab": _choice("checklists", "habitos", "evolucao"), "list_id": _text(60)}),
}


def validate_window_request(window_id: Any, params: Any) -> tuple[str, dict[str, Any]]:
    """Valida id e parâmetros. Levanta ValueError (pt-BR) se algo não estiver no registro."""
    if not isinstance(window_id, str) or window_id.strip() not in WINDOWS:
        raise ValueError(f"Janela desconhecida. Ids disponíveis: {', '.join(sorted(WINDOWS))}.")
    wid = window_id.strip()
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("Os parâmetros devem ser um objeto.")
    spec = WINDOWS[wid]
    clean: dict[str, Any] = {}
    for name, value in params.items():
        check = spec.params.get(name)
        if check is None:
            raise ValueError(f"Parâmetro '{name}' não existe na janela '{wid}'.")
        try:
            clean[name] = check(value)
        except ValueError as exc:
            raise ValueError(f"Parâmetro '{name}' {exc}.") from None
    return wid, clean


class OpenWindowTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_window"

    @property
    def description(self) -> str:
        titles = "; ".join(f"{wid} ({spec.title})" for wid, spec in WINDOWS.items())
        return (
            "Abre uma janela pronta dentro do painel do app (ex.: Finanças) para o usuário ver ou registrar "
            f"dados manualmente. Só aceita ids existentes: {titles}. Não altera dados; os parâmetros apenas "
            "escolhem o período da lista ou pré-preenchem o formulário, que o usuário confirma."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "window_id": {"type": "string", "enum": sorted(WINDOWS), "description": "Id da janela a abrir."},
                "params": {
                    "type": "object",
                    "description": (
                        "A janela pc-controls não aceita parâmetros. "
                        "Parâmetros opcionais da janela finance: period (week|month|all) escolhe o período da lista; "
                        "type (expense|income), category, amount, description e date (AAAA-MM-DD) apenas "
                        "pré-preenchem o formulário. Nada é gravado até o usuário salvar. "
                        "Janela places (busca de lugares com mapa): query (até 120 caracteres) e near (até 80) "
                        "preenchem a busca. Janela routines (Rotinas): routine_id opcional seleciona a rotina."
                    ),
                },
            },
            "required": ["window_id"],
        }

    def run(self, window_id: str = "", params: dict[str, Any] | None = None, command: str = "", **kwargs: Any) -> dict[str, Any]:
        # O caminho de marcadores envia só um texto em "command" (o id da janela).
        try:
            wid, clean = validate_window_request(window_id or command, params)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "message": f"Abrindo a janela {WINDOWS[wid].title}.",
            "ui_window": {"window_id": wid, "params": clean},
        }
