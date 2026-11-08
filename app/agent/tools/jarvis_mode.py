from typing import Any
from .base import BaseTool, ToolResult

class JarvisModeTool(BaseTool):
    """
    Controla o estado interno do sistema e modos de interação (Spotlight, Voz, Silencioso).
    """
    
    @property
    def name(self) -> str:
        return "jarvis_mode"
        
    @property
    def description(self) -> str:
        return (
            "Altera o modo de interação atual do assistente. "
            "Use 'silent' para mutar a voz (modo texto). "
            "Use 'hybrid' para voz normal. "
            "Use 'call_mode' para abrir interface de ligação."
        )
        
    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "O comando a executar: 'silent', 'hybrid', ou 'call_mode'",
                    "enum": ["silent", "hybrid", "call_mode"]
                }
            },
            "required": ["command"]
        }
        
    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        command = args.get("command", "")
        
        if command == "silent":
            return ToolResult(
                ok=True,
                message="Modo Silencioso ativado. Minhas respostas não serão mais faladas, apenas escritas.",
                data={"mode": "silent"}
            )
        elif command == "hybrid":
            return ToolResult(
                ok=True,
                message="Modo Híbrido ativado. Eu voltarei a falar as respostas.",
                data={"mode": "hybrid"}
            )
        elif command == "call_mode":
            return ToolResult(
                ok=True,
                message="Iniciando Modo Ligação...",
                data={"mode": "call_mode"}
            )
            
        return ToolResult(ok=False, message=f"Comando desconhecido: {command}")
