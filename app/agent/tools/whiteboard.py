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


class WhiteboardEditTool(BaseTool):
    """Permite ao tutor reorganizar e formatar elementos jÃ¡ existentes."""

    @property
    def name(self) -> str:
        return "whiteboard_edit"

    @property
    def description(self) -> str:
        return "Move, redimensiona, duplica, remove ou formata um elemento existente do quadro de estudos."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["list", "update", "move", "resize", "duplicate", "delete"]},
                "element_id": {"type": "string", "description": "ID do elemento no quadro."},
                "x": {"type": "number"}, "y": {"type": "number"}, "width": {"type": "number"}, "height": {"type": "number"},
                "color": {"type": "string"}, "size": {"type": "number"},
                "content": {"type": "string", "description": "Novo conteudo do bloco de texto."},
                "font_weight": {"type": "string", "enum": ["normal", "bold"]}, "font_style": {"type": "string", "enum": ["normal", "italic"]},
                "variant": {"type": "string", "enum": ["paragraph", "heading", "quote", "code", "callout"]}, "list_style": {"type": "string", "enum": ["plain", "bullets", "tasks"]},
                "background_color": {"type": "string"}, "font_family": {"type": "string"}, "text_decoration": {"type": "string", "enum": ["none", "underline", "line-through"]},
                "object_fit": {"type": "string", "enum": ["contain", "cover", "fill"]}, "opacity": {"type": "number"}, "caption": {"type": "string"},
                "rotation": {"type": "number"}, "z_index": {"type": "number"}, "locked": {"type": "boolean"},
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        session_id = (context or {}).get("session_id")
        if not session_id:
            return ToolResult(ok=False, message="Nenhuma sessao ativa foi fornecida ao quadro.")
        action = str(args.get("action") or "update")
        element_id = str(args.get("element_id") or "")
        data = _read()
        target_session = next((session for session in data.setdefault("sessions", []) if session.get("id") == session_id), None)
        if not target_session:
            return ToolResult(ok=False, message="Sessao de estudos nao encontrada.")
        board = target_session.setdefault("whiteboard", [])
        if action == "list":
            summary = [{"id": item.get("id"), "type": item.get("type"), "content": str(item.get("content", ""))[:120], "x": item.get("x", 0), "y": item.get("y", 0), "width": item.get("width"), "height": item.get("height"), "variant": item.get("variant"), "listStyle": item.get("listStyle"), "locked": item.get("locked", False)} for item in board]
            return ToolResult(ok=True, message=f"O quadro possui {len(summary)} elementos.", data={"elements": summary})
        if not element_id:
            return ToolResult(ok=False, message="Informe o element_id para editar o elemento.")
        index = next((i for i, item in enumerate(board) if item.get("id") == element_id), -1)
        if index < 0:
            return ToolResult(ok=False, message="Elemento do quadro nao encontrado.")
        if action == "delete":
            removed = board.pop(index)
            _write(data)
            return ToolResult(ok=True, message="Elemento removido do quadro.", data={"element": removed})
        if action == "duplicate":
            copy = dict(board[index])
            copy["id"] = str(uuid.uuid4())
            copy["x"] = float(copy.get("x", 0)) + 32
            copy["y"] = float(copy.get("y", 0)) + 32
            copy["zIndex"] = int(copy.get("zIndex", 0)) + 1
            board.append(copy)
            _write(data)
            return ToolResult(ok=True, message="Elemento duplicado no quadro.", data={"element": copy})
        item = board[index]
        keys = {"x", "y", "width", "height", "color", "size", "content", "font_weight", "font_style", "variant", "list_style", "background_color", "font_family", "text_decoration", "object_fit", "opacity", "caption", "rotation", "z_index", "locked"}
        for key in keys:
            if key in args and args[key] is not None:
                target_key = {"font_weight": "fontWeight", "font_style": "fontStyle", "list_style": "listStyle", "background_color": "backgroundColor", "font_family": "fontFamily", "text_decoration": "textDecoration", "object_fit": "objectFit", "z_index": "zIndex"}.get(key, key)
                item[target_key] = args[key]
        _write(data)
        return ToolResult(ok=True, message="Elemento atualizado no quadro de estudos.", data={"element": item})


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
