"""Ferramenta ``home``: casa pelo Home Assistant (fase contexto 3, opcional).

Só é oferecida ao modelo quando o Home Assistant está configurado (``allowed_tool_names``).
Passa pelo Action Kernel como qualquer ferramenta: o risco vem da operação e do domínio da
entidade (catálogo ``home``), então fechadura e alarme pedem aprovação na Central.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import BaseTool, ToolResult
from app.services import home_assistant as ha

OPERATIONS = ("list_entities", "get_state", "turn_on", "turn_off", "toggle", "set", "run_scene", "run_script")
NOT_CONFIGURED = "Desligado: Home Assistant não configurado."
MAX_LISTED = 40
_DONE = {"turn_on": "Ligado", "turn_off": "Desligado", "toggle": "Alternado"}


def _number(value: Any, low: float, high: float, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} inválido.")
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} inválido.") from None
    if not low <= number <= high:
        raise ValueError(f"{label} deve ficar entre {low:g} e {high:g}.")
    return number


class HomeTool(BaseTool):
    @property
    def name(self) -> str:
        return "home"

    @property
    def description(self) -> str:
        return (
            "Controla a casa pelo Home Assistant: lista aparelhos (list_entities, filtro opcional por cômodo), "
            "lê o estado (get_state), liga/desliga/alterna (turn_on, turn_off, toggle), ajusta brilho 0-100 "
            "ou temperatura 5-35 (set) e executa cenas e scripts (run_scene, run_script). "
            "Em 'entity' use o nome do aparelho como a pessoa falou (ex.: 'luz da sala') ou o entity_id."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "operation": {"type": "string", "enum": list(OPERATIONS), "description": "O que fazer."},
                "entity": {"type": "string", "description": "Nome do aparelho, cena ou script (ou entity_id)."},
                "brightness": {"type": "number", "description": "Só em set: brilho de 0 a 100 (%)."},
                "temperature": {"type": "number", "description": "Só em set: temperatura de 5 a 35 °C."},
                "area": {"type": "string", "description": "Só em list_entities: cômodo para filtrar."},
            },
            "required": ["operation"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        args = args or {}
        if not ha.is_configured():
            return ToolResult(False, NOT_CONFIGURED)
        operation = str(args.get("operation") or "").strip().lower()
        if operation not in OPERATIONS:
            return ToolResult(False, "Operação desconhecida. Use: " + ", ".join(OPERATIONS) + ".")
        try:
            if operation == "list_entities":
                return self._list(str(args.get("area") or ""))
            return self._act(operation, args)
        except (ValueError, ha.HomeAssistantError) as exc:
            return ToolResult(False, str(exc))

    def _list(self, area: str) -> ToolResult:
        entities = ha.list_entities()
        wanted = ha.normalize_name(area)
        if wanted:
            entities = [item for item in entities if wanted in ha.normalize_name(item["area"])]
        if not entities:
            return ToolResult(True, "Nenhum aparelho encontrado no Home Assistant" + (f" em '{area}'." if area else "."), data={"entities": []})
        lines = [f"{item['area']} / {item['domain']}: {item['name']} ({item['entity_id']}) = {item['state']}" for item in entities[:MAX_LISTED]]
        more = f" (+{len(entities) - MAX_LISTED} não listados)" if len(entities) > MAX_LISTED else ""
        return ToolResult(True, f"{len(entities)} aparelho(s){more}:\n" + "\n".join(lines), data={"entities": entities[:MAX_LISTED]})

    def _act(self, operation: str, args: dict[str, Any]) -> ToolResult:
        entity_name = str(args.get("entity") or "").strip()
        if not entity_name:
            return ToolResult(False, "Diga qual aparelho, cena ou script da casa.")
        domains = {"run_scene": ("scene",), "run_script": ("script",)}.get(operation)
        entity = ha.resolve(entity_name, domains)
        entity_id, domain = entity["entity_id"], entity["domain"]
        if operation == "get_state":
            state = ha.get_state(entity_id)
            extra = ", ".join(f"{key}: {value}" for key, value in state.get("attributes", {}).items())
            return ToolResult(True, f"{entity['name']} está {state.get('state') or 'sem estado'}" + (f" ({extra})." if extra else "."),
                              data={"entity_id": entity_id, "state": state.get("state"), "attributes": state.get("attributes", {})})
        if operation in ("run_scene", "run_script"):
            ha.call_service(domain, "turn_on", {"entity_id": entity_id})
            return ToolResult(True, f"{'Cena' if domain == 'scene' else 'Script'} '{entity['name']}' executado.", data={"entity_id": entity_id, "state": "executado"})
        if operation == "set":
            service, data, detail = self._set_call(domain, args)
            ha.call_service(service[0], service[1], {"entity_id": entity_id, **data})
            return ToolResult(True, f"{entity['name']}: {detail}.", data={"entity_id": entity_id, "state": detail})
        service_domain, service = ha.service_for(domain, operation)
        ha.call_service(service_domain, service, {"entity_id": entity_id})
        return ToolResult(True, f"{_DONE[operation]}: {entity['name']}.", data={"entity_id": entity_id, "state": operation})

    @staticmethod
    def _set_call(domain: str, args: dict[str, Any]) -> tuple[tuple[str, str], dict[str, Any], str]:
        if args.get("brightness") is not None:
            if domain != "light":
                raise ValueError("Brilho só vale para luzes.")
            level = int(round(_number(args["brightness"], 0, 100, "Brilho")))
            return ("light", "turn_on"), {"brightness_pct": level}, f"brilho em {level}%"
        if args.get("temperature") is not None:
            if domain != "climate":
                raise ValueError("Temperatura só vale para ar-condicionado e aquecedores (climate).")
            value = _number(args["temperature"], 5, 35, "Temperatura")
            return ("climate", "set_temperature"), {"temperature": value}, f"temperatura em {value:g} °C"
        raise ValueError("Em 'set', informe brightness (0-100) ou temperature (5-35).")
