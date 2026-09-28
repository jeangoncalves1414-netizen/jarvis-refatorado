from __future__ import annotations

import os
from typing import Any
from .base import BaseTool, ToolResult
from app.domain.file_manager import FileManagerService

class FileManagerTool(BaseTool):
    def __init__(self, base_folder: str | None = None) -> None:
        self.service = FileManagerService(base_folder=base_folder)

    @property
    def name(self) -> str:
        return "file_manager"

    @property
    def description(self) -> str:
        return "Lista arquivos ou lê o conteúdo de um arquivo de texto de forma segura."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read"],
                    "description": "Ação a ser executada: 'list' para ver diretório ou 'read' para ver conteúdo."
                },
                "path": {
                    "type": "string",
                    "description": "Caminho relativo do arquivo ou diretório."
                }
            },
            "required": ["action"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "list")
        path = args.get("path", "")

        try:
            if action == "list":
                items = self.service.list_directory(path)
                items_str = "\n".join([f"📁 {item}" if os.path.isdir(os.path.join(self.service.base_folder, path, item)) else f"📄 {item}" for item in items])
                return ToolResult(
                    ok=True,
                    message=f"Arquivos no diretório '{path or '.'}':\n{items_str}",
                    data={"items": items}
                )
            elif action == "read":
                content = self.service.read_file(path)
                # limitar o output para 1000 caracteres
                preview = content[:1000] + ("..." if len(content) > 1000 else "")
                return ToolResult(
                    ok=True,
                    message=f"Conteúdo de '{path}':\n\n{preview}",
                    data={"content": content}
                )
            else:
                return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
        except ValueError as e:
            # Check if this is a security-related error
            if "não permitido" in str(e).lower() or "autorizado" in str(e).lower():
                return ToolResult(ok=False, message="Erro de segurança: caminho não autorizado.")
            # Other ValueError handling
            return ToolResult(ok=False, message=f"Falha ao gerenciar arquivos: {e}")
        except Exception as e:
            return ToolResult(ok=False, message=f"Falha ao gerenciar arquivos: {e}")
