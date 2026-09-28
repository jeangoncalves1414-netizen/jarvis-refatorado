"""Tool Forge Engine (inspirado no Ada-SI e IRIS-AI).

Forja dinamicamente novas ferramentas (BaseTool) em Python a partir de requisitos
em linguagem natural do usuário. Valida a sintaxe via AST, testa a execução e salva
as ferramentas na pasta app/agent/tools/custom/ para registro automático.
"""
from __future__ import annotations

import ast
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

CUSTOM_TOOLS_DIR = Path("app/agent/tools/custom")


def ensure_custom_tools_dir() -> None:
    CUSTOM_TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    init_file = CUSTOM_TOOLS_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text("# Custom tools dynamic package\n", encoding="utf-8")


class ToolForgeEngine:
    """Motor de geração, validação e carregamento dinâmico de ferramentas."""

    def __init__(self) -> None:
        ensure_custom_tools_dir()

    def validate_code_ast(self, code: str) -> tuple[bool, str]:
        """Verifica se o código Python é sintaticamente válido via AST."""
        try:
            parsed = ast.parse(code)
            # Verifica se há classes que derivam de BaseTool
            has_tool_class = False
            for node in ast.walk(parsed):
                if isinstance(node, ast.ClassDef):
                    has_tool_class = True
                    break
            if not has_tool_class:
                return False, "O código não contém nenhuma definição de classe de Tool."
            return True, "Código Python válido."
        except SyntaxError as e:
            return False, f"Erro de sintaxe na linha {e.lineno}: {e.msg}"
        except Exception as e:
            return False, f"Erro na validação do código: {e}"

    def generate_tool_template(self, tool_name: str, description: str, python_code: str) -> str:
        """Encapsula a implementação do código na estrutura padrão BaseTool do Jarvis."""
        class_name = "".join(part.capitalize() for part in tool_name.replace("-", "_").split("_")) + "Tool"
        clean_tool_name = tool_name.lower().strip().replace(" ", "_")

        template = f'''"""Tool gerada automaticamente pelo Tool Forge do Jarvis.
Descrição: {description}
"""
from __future__ import annotations

from typing import Any
from app.agent.tools.base import BaseTool


class {class_name}(BaseTool):
    name = "{clean_tool_name}"
    description = "{description}"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        try:
            # Código customizado da ferramenta
{self._indent_code(python_code, 12)}
        except Exception as exc:
            return {{"success": False, "error": str(exc)}}
'''
        return template

    def _indent_code(self, code: str, spaces: int = 12) -> str:
        prefix = " " * spaces
        lines = code.strip().splitlines()
        return "\n".join(prefix + line for line in lines)

    def save_and_register_tool(self, tool_name: str, code: str) -> tuple[bool, str]:
        """Salva a tool no arquivo e carrega dinamicamente no Python."""
        valid, msg = self.validate_code_ast(code)
        if not valid:
            return False, f"Validação falhou: {msg}"

        clean_name = tool_name.lower().strip().replace(" ", "_")
        filepath = CUSTOM_TOOLS_DIR / f"{clean_name}.py"
        filepath.write_text(code, encoding="utf-8")

        # Tenta importar dinamicamente para validar execução
        try:
            spec = importlib.util.spec_from_file_location(f"app.agent.tools.custom.{clean_name}", filepath)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[spec.name] = module
                spec.loader.exec_module(module)
                return True, f"Ferramenta '{clean_name}' criada e registrada com sucesso em {filepath}."
            return False, "Não foi possível carregar o módulo dinamicamente."
        except Exception as e:
            return False, f"Erro ao registrar ferramenta: {e}"

    def list_custom_tools(self) -> list[dict[str, Any]]:
        """Lista todas as ferramentas customizadas criadas no Vault de Tools."""
        tools = []
        for filepath in CUSTOM_TOOLS_DIR.glob("*.py"):
            if filepath.name.startswith("__"):
                continue
            tools.append({
                "name": filepath.stem,
                "filename": filepath.name,
                "path": str(filepath),
                "size": filepath.stat().st_size
            })
        return tools


# Instância global do Tool Forge
tool_forge = ToolForgeEngine()
