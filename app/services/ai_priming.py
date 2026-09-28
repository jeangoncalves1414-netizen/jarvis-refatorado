"""
AI Priming System — Fase 6
Injeta contexto, notas de instrução e guias específicos antes da execução de tarefas complexas.
Inclui priming por tipo de tarefa, projeto ativo e conhecimento especializado.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PRIMING_NOTES_PATH = Path("data/priming_notes.json")

# Priming notes pré-definidas por contexto
DEFAULT_PRIMING_LIBRARY: dict[str, str] = {
    "code_review": (
        "⚡ PRIMING: Estou revisando código. Foque em:\n"
        "• Bugs e edge cases\n• Complexidade e performance\n"
        "• Legibilidade e boas práticas\n• Segurança e injeção de dados\n"
        "Responda com seções: [Bugs], [Performance], [Segurança], [Sugestões]."
    ),
    "brainstorm": (
        "🧠 PRIMING: Modo brainstorm ativo. Seja criativo, não filtre ideias por viabilidade.\n"
        "Liste pelo menos 10 ideias em bullets. Use pensamento lateral e conexões inesperadas."
    ),
    "study": (
        "📚 PRIMING: Modo de estudo ativo. Use a técnica Feynman: explique como se eu fosse um iniciante.\n"
        "Dê exemplos concretos, analogias e perguntas de revisão ao final."
    ),
    "planning": (
        "📋 PRIMING: Modo de planejamento. Estruture a resposta com:\n"
        "1. Objetivo principal\n2. Pré-requisitos\n3. Fases/Etapas numeradas\n"
        "4. Dependências e riscos\n5. Critério de sucesso."
    ),
    "debug": (
        "🔍 PRIMING: Modo debug. Analise o erro sistematicamente:\n"
        "1. Identifique o tipo de erro\n2. Traceback provável\n"
        "3. Hipóteses (do mais ao menos provável)\n4. Solução para cada hipótese."
    ),
    "write": (
        "✍️ PRIMING: Modo de escrita. Escreva de forma clara, engajante e bem estruturada.\n"
        "Use parágrafos curtos, voz ativa e linguagem precisa. Evite jargões desnecessários."
    ),
}


class AIPrimingSystem:
    """
    Sistema de Priming de IA para injetar contexto especializado antes de tarefas complexas.
    """

    def __init__(self) -> None:
        self._custom_notes: dict[str, str] = self._load_custom_notes()

    def _load_custom_notes(self) -> dict[str, str]:
        if not PRIMING_NOTES_PATH.exists():
            return {}
        try:
            with open(PRIMING_NOTES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_custom_notes(self) -> None:
        try:
            PRIMING_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(PRIMING_NOTES_PATH, "w", encoding="utf-8") as f:
                json.dump(self._custom_notes, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_custom_note(self, key: str, content: str) -> None:
        """Adiciona ou atualiza uma nota de priming customizada."""
        self._custom_notes[key.strip()] = content.strip()
        self._save_custom_notes()

    def remove_custom_note(self, key: str) -> bool:
        if key in self._custom_notes:
            del self._custom_notes[key]
            self._save_custom_notes()
            return True
        return False

    def get_priming_note(self, context_key: str) -> str | None:
        """Retorna nota de priming para o contexto especificado."""
        # Check custom notes first, then library
        note = self._custom_notes.get(context_key) or DEFAULT_PRIMING_LIBRARY.get(context_key)
        return note

    def detect_and_inject(self, user_message: str, system_prompt: str) -> str:
        """
        Detecta automaticamente o contexto da mensagem e injeta o priming appropriado.
        Retorna o system_prompt modificado.
        """
        msg_lower = user_message.lower()

        detected_key: str | None = None
        if any(kw in msg_lower for kw in ["revisar código", "review", "code review", "revisar"]):
            detected_key = "code_review"
        elif any(kw in msg_lower for kw in ["brainstorm", "ideias", "idéias", "ideas"]):
            detected_key = "brainstorm"
        elif any(kw in msg_lower for kw in ["estuda", "aprende", "aprendo", "explicar", "ensina"]):
            detected_key = "study"
        elif any(kw in msg_lower for kw in ["plano", "planeja", "roadmap", "etapas"]):
            detected_key = "planning"
        elif any(kw in msg_lower for kw in ["debug", "erro", "error", "bug", "traceback"]):
            detected_key = "debug"
        elif any(kw in msg_lower for kw in ["escreva", "redija", "write", "artigo", "texto"]):
            detected_key = "write"
        else:
            # Check custom notes keys
            for key in self._custom_notes:
                if key.lower() in msg_lower:
                    detected_key = key
                    break

        if detected_key:
            note = self.get_priming_note(detected_key)
            if note:
                return f"{system_prompt}\n\n{note}"

        return system_prompt

    def list_available_primings(self) -> dict[str, str]:
        """Lista todas as notas de priming disponíveis (padrão + custom)."""
        merged = {k: v[:80] + "..." for k, v in DEFAULT_PRIMING_LIBRARY.items()}
        merged.update({k: v[:80] + "..." for k, v in self._custom_notes.items()})
        return merged
