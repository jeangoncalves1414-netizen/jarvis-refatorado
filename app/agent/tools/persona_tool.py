"""Ferramenta nativa ``persona_tool``: gerencia configurações de persona, nome, tom e desafio matinal."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.agent.personas import (
    VALID_TONES,
    get_persona,
    update_persona,
    reset_persona,
)

ACTIONS = ["get", "update", "set_name", "set_tone", "set_challenge", "set_rules", "reset"]


class PersonaTool(BaseTool):
    @property
    def name(self) -> str:
        return "persona_tool"

    @property
    def description(self) -> str:
        return (
            "Gerencia a identidade, nome, tom de resposta e o desafio matinal do assistente. "
            "Use para consultar ou mudar nome (ex: 'mude seu nome para Sexta-Feira'), "
            "alterar o tom (amigável, formal, bem-humorado, militar, sarcástico leve), "
            "ativar/desativar ou alterar o desafio matinal (ex: 'mude o desafio para 20 agachamentos'), "
            "ou adicionar regras de comportamento."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ACTIONS,
                    "description": "Operação: get (consultar), update (atualizar), set_name, set_tone, set_challenge, set_rules, reset (restaurar padrão).",
                },
                "name": {
                    "type": "string",
                    "description": "Novo nome do assistente (ex: Sexta-Feira, Jarvis, etc.).",
                },
                "tone": {
                    "type": "string",
                    "enum": list(VALID_TONES.keys()),
                    "description": "Tom de resposta: amigável, formal, bem-humorado, militar, sarcástico leve.",
                },
                "morning_challenge_enabled": {
                    "type": "boolean",
                    "description": "Ativar (true) ou desativar (false) o desafio matinal de exercícios.",
                },
                "morning_challenge_text": {
                    "type": "string",
                    "description": "Texto descritivo do desafio matinal (ex: '10 flexões e 20 agachamentos').",
                },
                "custom_rules": {
                    "type": "string",
                    "description": "Regras ou instruções comportamentais específicas para a persona.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        return self.run(args)

    def run(self, arguments: dict[str, Any] | None = None) -> ToolResult:
        args = arguments or {}
        action = str(args.get("action") or "get").strip().lower()

        try:
            if action == "get":
                current = get_persona()
                challenge = current["morning_challenge"]
                status_ch = "ativado" if challenge.get("enabled") else "desativado"
                text = (
                    f"Configurações da Persona:\n"
                    f"• Nome: {current['name']}\n"
                    f"• Tom: {current['tone']} ({VALID_TONES.get(current['tone'], '')})\n"
                    f"• Desafio Matinal: {status_ch} (\"{challenge.get('text', '')}\")\n"
                    f"• Regras personalizadas: {current.get('custom_rules') or 'Nenhuma'}"
                )
                return ToolResult(True, text, data=current)

            if action == "reset":
                restored = reset_persona()
                return ToolResult(
                    True,
                    f"Persona restaurada para o padrão ({restored['name']}, tom {restored['tone']}).",
                    data=restored,
                )

            updates: dict[str, Any] = {}
            if action == "set_name" or "name" in args:
                updates["name"] = args.get("name")
            if action == "set_tone" or "tone" in args:
                updates["tone"] = args.get("tone")
            if action == "set_challenge":
                if "morning_challenge_enabled" in args:
                    updates["morning_challenge_enabled"] = args["morning_challenge_enabled"]
                if "morning_challenge_text" in args:
                    updates["morning_challenge_text"] = args["morning_challenge_text"]
            else:
                if "morning_challenge_enabled" in args:
                    updates["morning_challenge_enabled"] = args["morning_challenge_enabled"]
                if "morning_challenge_text" in args:
                    updates["morning_challenge_text"] = args["morning_challenge_text"]

            if action == "set_rules" or "custom_rules" in args:
                updates["custom_rules"] = args.get("custom_rules")

            updated = update_persona(updates)
            challenge = updated["morning_challenge"]
            ch_status = "ativado" if challenge.get("enabled") else "desativado"
            msg = (
                f"Persona atualizada com sucesso!\n"
                f"• Nome: {updated['name']}\n"
                f"• Tom: {updated['tone']}\n"
                f"• Desafio Matinal: {ch_status} (\"{challenge.get('text')}\")"
            )
            return ToolResult(True, msg, data=updated)

        except Exception as exc:
            return ToolResult(False, f"Erro ao gerenciar persona: {exc}")
