"""Ferramenta ``routine``: cria, lista, edita, ativa, apaga e executa rotinas gravadas.

Rotina = nome + etapas (ferramenta, operação, parâmetros, espera antes, se falhar) + gatilhos
(horário em America/Sao_Paulo, frase de voz, comando "/"). Cada execução vira um Run de origem
``routine`` e cada etapa passa pelo Action Kernel (risco e aprovação valem como no chat).
"""
from __future__ import annotations

from typing import Any

from .base import BaseTool, ToolResult

ACTIONS = ["create", "list", "update", "enable", "disable", "delete", "run_now", "next_runs"]

_STEP_SCHEMA = {
    "type": "object",
    "properties": {
        "tool": {"type": "string", "description": "Ferramenta da etapa (ex.: open_windows_app, spotify, web_search)."},
        "operation": {"type": "string", "description": "Valor do argumento action da ferramenta (ex.: open, search_play, open_url)."},
        "params": {"type": "object", "description": "Demais argumentos da ferramenta (ex.: {\"app_name\": \"chrome\"} ou {\"query\": \"Foco\"})."},
        "delay_before": {"type": "integer", "description": "Segundos de espera ANTES desta etapa (0 a 3600)."},
        "on_failure": {"type": "string", "enum": ["stop", "continue", "retry"], "description": "Se falhar: parar, continuar ou tentar de novo."},
        "retries": {"type": "integer", "description": "Tentativas extras com retry (1 a 3)."},
        "timeout": {"type": "integer", "description": "Tempo limite da etapa em segundos (5 a 600), opcional."},
        "label": {"type": "string", "description": "Nome curto da etapa, opcional."},
    },
    "required": ["tool"],
}

_TRIGGER_SCHEMA = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["at", "daily", "weekdays", "weekly", "interval", "voice", "command"]},
        "time": {"type": "string", "description": "HH:MM para daily, weekdays e weekly."},
        "days": {"type": "array", "items": {"type": "string"}, "description": "weekly: mon, tue, wed, thu, fri, sat, sun."},
        "minutes": {"type": "integer", "description": "interval: a cada N minutos (5 a 1440)."},
        "datetime": {"type": "string", "description": "at: AAAA-MM-DDTHH:MM no horário de São Paulo."},
        "phrase": {"type": "string", "description": "voice: frase que dispara a rotina."},
        "slash": {"type": "string", "description": "command: palavra do comando /palavra."},
    },
    "required": ["type"],
}


def _service():
    from app.routines.service import routine_service
    return routine_service


def _find(args: dict[str, Any]) -> dict[str, Any]:
    from app.routines.models import RoutineError, normalize_text

    service = _service()
    routine_id = str(args.get("routine_id") or "").strip()
    if routine_id:
        return service.get(routine_id)
    wanted = normalize_text(args.get("name"))
    if wanted:
        for routine in service.store().list():
            if normalize_text(routine["name"]) == wanted:
                return routine
    raise RoutineError("Informe o routine_id ou o nome exato da rotina (use action=list para ver).")


def _summary(described: dict[str, Any]) -> list[str]:
    from app.routines.models import describe_steps

    triggers = ", ".join(described.get("trigger_labels") or []) or "só manual"
    lines = [f'Rotina "{described["name"]}" ({triggers}).', *describe_steps(described, limit=5)]
    if described.get("next_run"):
        lines.append(f"Próxima execução: {described['next_run_label']}.")
    return lines


class RoutineTool(BaseTool):
    @property
    def name(self) -> str:
        return "routine"

    @property
    def description(self) -> str:
        return (
            "Rotinas gravadas: sequência de ações com horário (todo dia, dias úteis, semanal, a cada N min, data), "
            "frase de voz ou comando /. Use para pedidos com horário ou repetição (ex.: 'todo dia às 8h abre o Chrome "
            "e 30 s depois toca a playlist Foco'). Para fazer algo agora com espera, NÃO use rotina: use as ferramentas "
            "e wait. Espera entre etapas = delay_before da etapa seguinte."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ACTIONS, "description": "Operação."},
                "routine_id": {"type": "string", "description": "Id da rotina (update, enable, disable, delete, run_now)."},
                "name": {"type": "string", "description": "Nome da rotina (create) ou nome exato para achar uma rotina."},
                "steps": {"type": "array", "items": _STEP_SCHEMA, "description": "Etapas em ordem (create/update)."},
                "triggers": {"type": "array", "items": _TRIGGER_SCHEMA, "description": "Gatilhos (create/update)."},
                "quiet_hours": {"type": "object", "description": "Horário de silêncio {start: HH:MM, end: HH:MM}, opcional."},
                "catch_up_minutes": {"type": "integer", "description": "Tolerância se o PC estava desligado (0 a 720 min, padrão 15)."},
                "run_now": {"type": "boolean", "description": "create: executar também agora."},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        from app.routines.models import RoutineError
        from app.routines.runner import RoutineBusy
        from app.routines.service import RoutineNotFound

        args = args or {}
        action = str(args.get("action") or "list").strip().lower()
        service = _service()
        try:
            if action == "list":
                items = service.list_with_next()
                if not items:
                    return ToolResult(True, "Nenhuma rotina criada ainda.", data={"routines": [], "routine_ids": []})
                lines = [
                    f'- {item["name"]} ({item["id"]}): {", ".join(item["trigger_labels"]) or "só manual"}; '
                    f'{"ativa" if item["enabled"] else "desativada"}; próxima: {item["next_run_label"]}'
                    for item in items
                ]
                return ToolResult(True, "Rotinas:\n" + "\n".join(lines), data={"routines": items, "routine_ids": [item["id"] for item in items]})
            if action == "next_runs":
                upcoming = service.next_runs(10)
                if not upcoming:
                    return ToolResult(True, "Nenhuma execução agendada.", data={"next_runs": []})
                return ToolResult(True, "Próximas execuções:\n" + "\n".join(f'- {item["label"]}: {item["name"]}' for item in upcoming), data={"next_runs": upcoming})
            if action == "create":
                payload = {key: args[key] for key in ("name", "steps", "triggers", "catch_up_minutes") if key in args}
                if "quiet_hours" in args:
                    payload["quiet"] = args["quiet_hours"]
                payload["run_now"] = args.get("run_now") is True
                payload["_origin"] = "agent"
                created = service.create(payload)
                described = created["routine"]
                message = "Criada. " + " ".join(_summary(described))
                if created.get("run_id"):
                    message += " Execução iniciada agora; acompanhe na Central."
                return ToolResult(True, message, data={"routine": described, "next_run": created["next_run"], "routine_ids": [described["id"]], "run_id": created.get("run_id")})
            if action not in ACTIONS:
                return ToolResult(False, f"Operação desconhecida: {action}. Use: {', '.join(ACTIONS)}.")
            routine = _find(args)
            routine_id = routine["id"]
            if action == "update":
                payload = {key: args[key] for key in ("name", "steps", "triggers", "catch_up_minutes") if key in args}
                if "quiet_hours" in args:
                    payload["quiet"] = args["quiet_hours"]
                updated = service.update(routine_id, payload)
                described = updated["routine"]
                return ToolResult(True, "Atualizada. " + " ".join(_summary(described)), data={"routine": described, "next_run": updated["next_run"], "routine_ids": [routine_id]})
            if action in ("enable", "disable"):
                described = service.set_enabled(routine_id, action == "enable")
                state = "ativada" if action == "enable" else "desativada"
                extra = f" Próxima execução: {described['next_run_label']}." if described.get("next_run") else ""
                return ToolResult(True, f'Rotina "{described["name"]}" {state}.{extra}', data={"routine": described, "routine_ids": [routine_id]})
            if action == "delete":
                service.delete(routine_id)
                return ToolResult(True, f'Rotina "{routine["name"]}" apagada, com o histórico.', data={"routine_ids": [routine_id]})
            run_id = service.run_now(routine_id, trigger_kind="agent")
            return ToolResult(True, f'Rotina "{routine["name"]}" iniciada. Acompanhe na Central.', data={"run_id": run_id, "routine_ids": [routine_id]})
        except (RoutineError, RoutineNotFound, RoutineBusy) as exc:
            return ToolResult(False, str(exc.args[0] if exc.args else exc))
