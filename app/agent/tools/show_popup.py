"""Ferramenta show_popup: o agente pede um popup pronto do painel (lote 6, Fase 3).

Só escolhe um modelo de ``app.agent.popups.POPUP_TEMPLATES`` e preenche seletores validados.
Os dados do popup são montados pelo backend no gancho do Action Kernel, depois que esta
ação dá certo; aqui só a validação acontece. Nenhum dado é alterado.
"""
from __future__ import annotations

from typing import Any

from app.agent.popups import POPUP_TEMPLATES, validate_popup_request
from app.agent.tools.base import BaseTool


class ShowPopupTool(BaseTool):
    @property
    def name(self) -> str:
        return "show_popup"

    @property
    def description(self) -> str:
        models = "; ".join(f"{tid} ({spec.description})" for tid, spec in POPUP_TEMPLATES.items())
        return (
            "Mostra um popup animado no painel do app. Popups de hábitos, agenda e água aparecem sozinhos "
            "depois das ferramentas habit_tool, calendar e lifeos_tool: não chame esta ferramenta para eles. "
            "Use só quando a usuária pedir para ver algo ('mostra minha água') ou para anotações ao vivo "
            "('anota o que eu for falando' → live_notes, que escreve a fala e salva no cofre). "
            f"Modelos: {models}. Não altera dados."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "template": {"type": "string", "enum": sorted(POPUP_TEMPLATES), "description": "Modelo do popup."},
                "params": {
                    "type": "object",
                    "description": (
                        "Parâmetros do modelo. info: title (até 60 caracteres, obrigatório), "
                        "lines (lista de até 6 textos de até 120 caracteres), tone (info|ok|warn). "
                        "habit_list: filter (today|all), highlight (nomes). schedule: date (AAAA-MM-DD). "
                        "water: nenhum. live_notes: title (até 80), format (text|bullets|checklist), dictate (bool)."
                    ),
                },
            },
            "required": ["template"],
        }

    def run(self, template: str = "", params: dict[str, Any] | None = None, command: str = "", **kwargs: Any) -> dict[str, Any]:
        try:
            tid, clean = validate_popup_request(template or command, params)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "message": f"Mostrando o popup {POPUP_TEMPLATES[tid].title}.",
            "ui_popup": {"template": tid, "params": clean},
        }
