from __future__ import annotations

import json
from typing import Any
from .base import BaseTool, ToolResult
from app.core.actions import ToolMetadata


BUILTIN_RECIPES: dict[str, dict[str, Any]] = {
    "planejamento_semanal": {
        "name": "Planejamento semanal", "purpose": "Abrir e preparar o espaço de planejamento.",
        "capabilities": ["planning_workspace"], "confirmation_boundary": False,
        "steps": [{"tool": "planning_workspace", "action": "open"}],
    },
    "encerrar_dia": {
        "name": "Encerrar o dia", "purpose": "Revisar pendências sem apagar dados.",
        "capabilities": ["planning_workspace"], "confirmation_boundary": False,
        "steps": [{"tool": "planning_workspace", "action": "status"}],
    },
}


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate the deliberately small declarative workflow language."""
    if not isinstance(recipe, dict) or not isinstance(recipe.get("name"), str):
        raise ValueError("Workflow precisa de nome.")
    capabilities = recipe.get("capabilities")
    steps = recipe.get("steps")
    if not isinstance(capabilities, list) or not capabilities or not isinstance(steps, list) or not steps:
        raise ValueError("Workflow precisa declarar capacidades e etapas.")
    for step in steps:
        if not isinstance(step, dict) or set(step) - {"tool", "action", "title", "content", "variables"}:
            raise ValueError("Etapa de workflow contém campos não permitidos.")
        tool = step.get("tool")
        if not isinstance(tool, str) or tool not in capabilities:
            raise ValueError("Workflow tentou usar ferramenta fora das capacidades declaradas.")
        if any(word in str(value).lower() for value in step.values() for word in ("script", "subprocess", "shell")):
            raise ValueError("Workflows não aceitam código executável.")
    return recipe


class WorkflowTool(BaseTool):
    @property
    def name(self) -> str:
        return "workflow"
    
    @property
    def description(self) -> str:
        return "Executa receitas declarativas, revisáveis e seguras em modo simulação."

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(capabilities=("workflow",), default_risk="high", requires_confirmation=True)
    
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "recipe": {"type": "object", "description": "Receita declarativa validada."},
                "recipe_id": {"type": "string", "enum": list(BUILTIN_RECIPES)},
                "dry_run": {"type": "boolean", "description": "Obrigatório; mostra efeitos sem executar."},
            },
            "required": []
        }
    
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        recipe_id = str(args.get("recipe_id") or "")
        recipe = BUILTIN_RECIPES.get(recipe_id) if recipe_id else args.get("recipe")
        try:
            recipe = validate_recipe(dict(recipe or {}))
        except (TypeError, ValueError) as exc:
            return ToolResult(False, f"Workflow inválido: {exc}")
        if not bool(args.get("dry_run", True)):
            return ToolResult(False, "Por segurança, workflows exigem uma simulação antes da execução.")
        preview = [{"tool": step["tool"], "action": step.get("action", "") } for step in recipe["steps"]]
        return ToolResult(True, f"Simulação pronta: {recipe['name']} ({len(preview)} etapa(s)).", {
            "dry_run": True, "recipe": recipe["name"], "steps": preview,
        })
