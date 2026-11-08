"""Ferramenta para controle do Assistente Proativo (Briefing Matinal e Lembretes)."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.proactive import ProactiveService


class ProactiveAgentTool(BaseTool):
    def __init__(self, service: ProactiveService | None = None) -> None:
        self.service = service or ProactiveService()

    @property
    def name(self) -> str:
        return "proactive_agent"

    @property
    def description(self) -> str:
        return (
            "Gerencia o comportamento proativo do assistente: configura o briefing matinal (horário, tópicos, "
            "instruções personalizadas em linguagem natural) e agenda lembretes por voz temporizados (ex: às 13:00 ou em +30m)."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["configure_briefing", "add_reminder", "get_status", "trigger_briefing"],
                    "description": (
                        "Ação: 'configure_briefing' (alterar horário, tópicos ou instruções do briefing), "
                        "'add_reminder' (agendar lembrete com horário), 'get_status' (ver status atual), "
                        "'trigger_briefing' (executar briefing agora)."
                    ),
                },
                "enabled": {
                    "type": "boolean",
                    "description": "Ativar ou desativar o briefing matinal proativo.",
                },
                "briefing_time": {
                    "type": "string",
                    "description": "Horário do briefing no formato HH:MM (ex: '08:00', '07:30').",
                },
                "topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Lista de tópicos a incluir no briefing (opções: 'weather', 'news', 'finance', 'holidays').",
                },
                "custom_instructions": {
                    "type": "string",
                    "description": "Instruções personalizadas em linguagem natural para ajustar o que o assistente fala de manhã (ex: 'não fale de clima', 'remova finanças').",
                },
                "reminder_message": {
                    "type": "string",
                    "description": "Mensagem ou assunto do lembrete a agendar.",
                },
                "reminder_time": {
                    "type": "string",
                    "description": "Horário de disparo do lembrete: pode ser horário exato '13:00' ou relativo '+30m' / '+1h'.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action")
        if not action:
            return ToolResult(ok=False, message="Ação é obrigatória.")

        if action == "configure_briefing":
            enabled = args.get("enabled")
            b_time = args.get("briefing_time")
            topics = args.get("topics")
            instructions = args.get("custom_instructions")

            updated = self.service.update_briefing_config(
                enabled=enabled,
                briefing_time=b_time,
                topics=topics,
                custom_instructions=instructions,
            )
            msg = (
                f"Configuração do Briefing Matinal atualizada:\n"
                f"- Ativado: {updated.get('briefing_enabled')}\n"
                f"- Horário: {updated.get('briefing_time')}\n"
                f"- Tópicos: {', '.join(updated.get('briefing_topics', []))}\n"
                f"- Instruções: {updated.get('custom_instructions') or 'Nenhuma'}"
            )
            return ToolResult(ok=True, message=msg, data=updated)

        elif action == "add_reminder":
            msg_text = str(args.get("reminder_message") or "").strip()
            r_time = str(args.get("reminder_time") or "").strip()
            if not msg_text or not r_time:
                return ToolResult(ok=False, message="Mensagem ('reminder_message') e horário ('reminder_time') são obrigatórios.")

            reminder = self.service.add_reminder(message=msg_text, target_time_str=r_time)
            msg = f"Lembrete agendado com sucesso para {reminder['target_time']}: '{reminder['message']}'"
            return ToolResult(ok=True, message=msg, data=reminder)

        elif action == "get_status":
            cfg = self.service.get_config()
            pending = self.service.get_pending_reminders()
            lines = [
                "Status do Assistente Proativo:",
                f"- Briefing Matinal: {'Ativado' if cfg.get('briefing_enabled') else 'Desativado'} (Horário: {cfg.get('briefing_time')})",
                f"- Tópicos do Briefing: {', '.join(cfg.get('briefing_topics', []))}",
                f"- Instruções Customizadas: {cfg.get('custom_instructions') or 'Nenhuma'}",
                f"- Lembretes Pendentes ({len(pending)}):",
            ]
            for r in pending:
                lines.append(f"  • [{r['target_time']}] {r['message']}")
            return ToolResult(ok=True, message="\n".join(lines), data={"config": cfg, "pending": pending})

        elif action == "trigger_briefing":
            briefing_text = self.service.generate_briefing_text()
            return ToolResult(ok=True, message=briefing_text, data={"briefing": briefing_text})

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
