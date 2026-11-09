"""Inventário das ferramentas do agente: operações, risco, efeito e parâmetros.

Lê o registro e o catálogo do Action Kernel; nada é executado. Uso:
``python -m app.agent.tools.inventory`` imprime a tabela em Markdown.
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import GENERAL_TOOL_NAMES, TUTOR_TOOL_NAMES, ToolRegistry

# Argumentos que escolhem a operação, na ordem em que o catálogo os procura.
_OPERATION_KEYS = ("action", "command", "source", "format")


def _operation_key(parameters: dict[str, Any], metadata: Any) -> str:
    properties = parameters.get("properties") or {}
    for key in (*getattr(metadata, "operation_arguments", ()), *_OPERATION_KEYS):
        if isinstance(properties.get(key), dict) and properties[key].get("enum"):
            return key
    return ""


def _parameter_summary(name: str, schema: Any) -> dict[str, Any]:
    schema = schema if isinstance(schema, dict) else {}
    item: dict[str, Any] = {"name": name, "type": str(schema.get("type") or "?")}
    if schema.get("enum"):
        item["enum"] = list(schema["enum"])
    if schema.get("type") == "array" and isinstance(schema.get("items"), dict):
        inner = schema["items"]
        item["items"] = str(inner.get("type") or "?")
        if isinstance(inner.get("properties"), dict):
            item["fields"] = sorted(inner["properties"])
    return item


def build_inventory(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Uma linha por ferramenta registrada, em ordem alfabética."""
    rows: list[dict[str, Any]] = []
    for tool in sorted(registry.list_tools(), key=lambda t: t.name):
        metadata = registry.get_tool_metadata(tool.name)
        parameters = tool.parameters or {}
        key = _operation_key(parameters, metadata)
        operations = []
        if key:
            for operation in parameters["properties"][key]["enum"]:
                arguments = {key: operation}
                operations.append({
                    "operation": operation,
                    "risk": metadata.risk_for(arguments),
                    "effect": metadata.effect_for(arguments),
                })
        rows.append({
            "tool": tool.name,
            "general": tool.name in GENERAL_TOOL_NAMES,
            "tutor": tool.name in TUTOR_TOOL_NAMES,
            "in_catalog": tool.name in TOOL_CATALOG,
            "default_risk": metadata.risk_for({}),
            "effect": metadata.effect_for({}) or metadata.effect,
            "operation_key": key,
            "operations": operations,
            "parameters": [_parameter_summary(name, schema) for name, schema in (parameters.get("properties") or {}).items()],
            "required": list(parameters.get("required") or []),
        })
    return rows


def _escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _format_parameter(item: dict[str, Any], required: list[str]) -> str:
    text = f"{item['name']}{'*' if item['name'] in required else ''}: {item['type']}"
    if item.get("enum"):
        text += " (" + "/".join(str(v) for v in item["enum"]) + ")"
    if item.get("fields"):
        text += " [" + ", ".join(item["fields"]) + "]"
    elif item.get("items"):
        text += f"[{item['items']}]"
    return text


def render_markdown(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| Ferramenta | Visível | Catálogo | Operações (risco) | Parâmetros (* obrigatório) |",
        "|---|---|---|---|---|",
    ]
    for row in rows:
        visible = "geral" if row["general"] else ("tutor" if row["tutor"] else "não")
        if row["operations"]:
            operations = ", ".join(f"{op['operation']} ({op['risk']})" for op in row["operations"])
        else:
            operations = f"— ({row['default_risk']})"
        parameters = "; ".join(_format_parameter(item, row["required"]) for item in row["parameters"]) or "—"
        lines.append(
            f"| {row['tool']} | {visible} | {'sim' if row['in_catalog'] else 'não'} | {_escape(operations)} | {_escape(parameters)} |"
        )
    lines.append("")
    lines.append("## Efeitos por operação")
    lines.append("")
    for row in rows:
        if not row["general"]:
            continue
        if row["operations"]:
            for op in row["operations"]:
                lines.append(f"- `{row['tool']}.{op['operation']}` ({op['risk']}): {op['effect'] or '(sem efeito declarado)'}")
        else:
            lines.append(f"- `{row['tool']}` ({row['default_risk']}): {row['effect'] or '(sem efeito declarado)'}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(render_markdown(build_inventory(ToolRegistry())))
