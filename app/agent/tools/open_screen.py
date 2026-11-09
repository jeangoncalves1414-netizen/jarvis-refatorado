"""Ferramenta open_screen: pede ao painel que mude para uma tela pronta do app.

O agente só escolhe um id da lista abaixo (espelho de ``frontend/src/navigation.ts``).
O resultado segue no contexto da resposta (``context.tool_results.open_screen.data.ui_screen``)
e o painel valida o id de novo antes de trocar de tela. Nenhum dado é alterado.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool
from app.agent.tools.lifestyle_tools import normalize_name

# Ids persistidos das telas (iguais aos de frontend/src/navigation.ts) e o rótulo visível.
SCREENS: dict[str, str] = {
    "Dashboard": "Início",
    "Chat": "Conversas",
    "Central": "Execuções",
    "Automações": "Automações",
    "Memórias": "Conhecimento",
    "Integrações": "Integrações",
    "Estudos": "Estudos",
    "Evolução": "Life OS",
    "Calendário": "Calendário",
    "Painel pessoal": "Painel pessoal",
    "Análises": "Métricas",
    "Identidade": "Perfis",
    "Configurações": "Configurações",
}

# Apelidos em português (sem acento, minúsculos). "painel" sem qualificador = Painel pessoal (decisão 10).
SCREEN_ALIASES: dict[str, str] = {
    "inicio": "Dashboard", "home": "Dashboard", "dashboard": "Dashboard",
    "conversas": "Chat", "conversa": "Chat", "chat": "Chat",
    "central": "Central", "execucoes": "Central", "aprovacoes": "Central",
    "automacoes": "Automações", "rotinas": "Automações",
    "memorias": "Memórias", "conhecimento": "Memórias",
    "integracoes": "Integrações",
    "estudos": "Estudos", "estudo": "Estudos",
    "evolucao": "Evolução", "life os": "Evolução", "lifeos": "Evolução",
    "calendario": "Calendário", "agenda": "Calendário",
    "painel": "Painel pessoal", "painel pessoal": "Painel pessoal", "habitos": "Painel pessoal", "tarefas": "Painel pessoal",
    "analises": "Análises", "metricas": "Análises",
    "identidade": "Identidade", "perfis": "Identidade",
    "configuracoes": "Configurações", "ajustes": "Configurações",
}


def resolve_screen(value: Any) -> str:
    """Id da tela a partir do id ou de um apelido. Levanta ValueError (pt-BR) se não existir."""
    if isinstance(value, str):
        text = value.strip()
        if text in SCREENS:
            return text
        normalized = normalize_name(text)
        for screen_id in SCREENS:
            if normalize_name(screen_id) == normalized:
                return screen_id
        if normalized in SCREEN_ALIASES:
            return SCREEN_ALIASES[normalized]
    raise ValueError("Tela desconhecida. Telas disponíveis: " + ", ".join(SCREENS) + ".")


class OpenScreenTool(BaseTool):
    @property
    def name(self) -> str:
        return "open_screen"

    @property
    def description(self) -> str:
        return (
            "Muda o app para uma das telas prontas. Use quando a usuária pedir para abrir/ir para uma tela: "
            "'abre o painel' → Painel pessoal (hábitos, tarefas, indicadores); 'Life OS'/'evolução' → Evolução; "
            "'agenda' → Calendário; 'execuções'/'aprovações' → Central; 'configurações' → Configurações. "
            "Para janelas flutuantes (Finanças, Controles do PC) use open_window. Não altera dados."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "screen": {"type": "string", "enum": list(SCREENS), "description": "Id da tela a abrir."},
            },
            "required": ["screen"],
        }

    def run(self, screen: str = "", command: str = "", **kwargs: Any) -> dict[str, Any]:
        # O caminho de marcadores envia só um texto em "command".
        try:
            screen_id = resolve_screen(screen or command)
        except ValueError as exc:
            return {"ok": False, "error": str(exc)}
        return {
            "ok": True,
            "message": f"Abrindo a tela {SCREENS[screen_id]}.",
            "ui_screen": {"screen": screen_id},
        }
