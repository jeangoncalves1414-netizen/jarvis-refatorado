from __future__ import annotations

import uuid
from typing import Any
from .base import BaseTool, ToolResult
from .whiteboard_layout import resolve_y
from app.storage.session_store import _read, _write

class WhiteboardAddTextTool(BaseTool):
    @property
    def name(self) -> str:
        return "whiteboard_add_text"

    @property
    def description(self) -> str:
        return "Adiciona um bloco de texto explicativo em coordenadas específicas do quadro negro."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Texto/conteúdo explicativo a ser adicionado (pode conter markdown simples)."
                },
                "x": {
                    "type": "number",
                    "description": "Coordenada X horizontal no quadro infinito (ex: 100)."
                },
                "y": {
                    "type": "number",
                    "description": "Coordenada Y vertical no quadro infinito (ex: 150)."
                },
                "size": {
                    "type": "integer",
                    "description": "Tamanho da fonte em pixels (padrão: 16)."
                },
                "color": {
                    "type": "string",
                    "description": "Cor hexadecimal do texto (padrão: '#ffffff')."
                }
            },
            "required": ["text", "x", "y"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        session_id = (context or {}).get("session_id")
        if not session_id:
            return ToolResult(ok=False, message="Nenhuma sessão ativa fornecida no contexto.")

        text = args.get("text", "").strip()
        x = float(args.get("x", 0))
        y = float(args.get("y", 0))
        size = int(args.get("size", 16))
        color = args.get("color", "#ffffff").strip()

        data = _read()
        target_session = None
        for s in data.setdefault("sessions", []):
            if s.get("id") == session_id:
                target_session = s
                break

        if not target_session:
            target_session = {"id": session_id, "title": "Sessão Tutor", "history": []}
            data["sessions"].append(target_session)

        board = target_session.setdefault("whiteboard", [])
        y = resolve_y(board, y, text=text)
        element = {
            "id": str(uuid.uuid4()),
            "type": "text",
            "content": text,
            "x": x,
            "y": y,
            "size": size,
            "color": color
        }
        board.append(element)
        _write(data)

        return ToolResult(
            ok=True,
            message=f"Texto adicionado ao quadro negro em ({x}, {y}): '{text[:30]}...'",
            data=element
        )


class WhiteboardAddImageTool(BaseTool):
    @property
    def name(self) -> str:
        return "whiteboard_add_image"

    @property
    def description(self) -> str:
        return "Adiciona uma imagem explicativa em coordenadas específicas do quadro negro."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "image_url": {
                    "type": "string",
                    "description": "URL da imagem na web ou caminho local de imagem."
                },
                "x": {
                    "type": "number",
                    "description": "Coordenada X no quadro infinito."
                },
                "y": {
                    "type": "number",
                    "description": "Coordenada Y no quadro infinito."
                },
                "width": {
                    "type": "integer",
                    "description": "Largura da imagem em pixels (padrão: 250)."
                },
                "height": {
                    "type": "integer",
                    "description": "Altura da imagem em pixels (padrão: 180)."
                }
            },
            "required": ["image_url", "x", "y"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        session_id = (context or {}).get("session_id")
        if not session_id:
            return ToolResult(ok=False, message="Nenhuma sessão ativa fornecida no contexto.")

        url = args.get("image_url", "").strip()
        x = float(args.get("x", 0))
        y = float(args.get("y", 0))
        width = int(args.get("width", 250))
        height = int(args.get("height", 180))

        data = _read()
        target_session = None
        for s in data.setdefault("sessions", []):
            if s.get("id") == session_id:
                target_session = s
                break

        if not target_session:
            target_session = {"id": session_id, "title": "Sessão Tutor", "history": []}
            data["sessions"].append(target_session)

        board = target_session.setdefault("whiteboard", [])
        y = resolve_y(board, y, is_image=True, height=height)
        element = {
            "id": str(uuid.uuid4()),
            "type": "image",
            "content": url,
            "x": x,
            "y": y,
            "width": width,
            "height": height
        }
        board.append(element)
        _write(data)

        return ToolResult(
            ok=True,
            message=f"Imagem adicionada ao quadro negro em ({x}, {y}): '{url}'",
            data=element
        )


class WhiteboardClearTool(BaseTool):
    @property
    def name(self) -> str:
        return "whiteboard_clear"

    @property
    def description(self) -> str:
        return "Limpa completamente todos os elementos do quadro negro desta sessão."

    @property
    def parameters(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        session_id = (context or {}).get("session_id")
        if not session_id:
            return ToolResult(ok=False, message="Nenhuma sessão ativa fornecida no contexto.")

        data = _read()
        for s in data.setdefault("sessions", []):
            if s.get("id") == session_id:
                s["whiteboard"] = []
                _write(data)
                return ToolResult(ok=True, message="Quadro negro limpo com sucesso.")
        
        return ToolResult(ok=True, message="Quadro negro já estava limpo ou sessão não existe.")
