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
        return "Gerencia arquivos locais: lista, lê, cria diretórios e cria arquivos de texto sem sobrescrever existentes. Use create para criar texto, sem script_runner."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "read", "mkdir", "create"],
                    "description": "Ação a ser executada: 'list' para ver diretório, 'read' para ver conteúdo ou 'mkdir' para criar pasta."
                },
                "content": {"type": "string", "description": "create: conteúdo UTF-8 do novo arquivo; não sobrescreve arquivos existentes."},
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
            elif action == "create":
                created = self.service.create_file(path, args.get("content", ""))
                return ToolResult(True, f"Arquivo criado: '{path}'.", {"path": str(created)})
            elif action in ("mkdir", "create_dir"):
                created_p = self.service.create_directory(path)
                return ToolResult(
                    ok=True,
                    message=f"Pasta criada com sucesso: '{path}' (caminho: {created_p})",
                    data={"path": str(created_p)}
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
