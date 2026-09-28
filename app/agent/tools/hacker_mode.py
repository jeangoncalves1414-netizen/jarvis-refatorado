"""Hacker Mode Tool: Execução segura de scripts e comandos de terminal com motor Hacker.ai."""
from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.hacker_terminal import hacker_terminal


class HackerModeTool(BaseTool):
    name = "hacker_mode"
    description = "Executa comandos de terminal e scripts com controle de permissão e explicação por IA."

    def run(self, command: str = "", script: str = "", force: bool = False, **kwargs: Any) -> dict[str, Any]:
        cmd = (command or script).strip()
        if not cmd:
            return {"success": False, "error": "Nenhum comando ou script fornecido."}

        res = hacker_terminal.prepare_or_execute(cmd, force_approved=force)
        return res

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        cmd = str(args.get("command") or args.get("script") or "").strip()
        force = bool(args.get("force", False))
        if not cmd:
            return ToolResult(ok=False, message="Comando não informado.")

        res = self.run(command=cmd, force=force)
        if res.get("status") == "pending_approval":
            msg = (
                f"🔒 AVISO DE SEGURANÇA (Hacker Mode):\n"
                f"Comando: `{cmd}`\n"
                f"Explicação da IA: {res.get('explanation')}\n"
                f"Para executar, confirme via API ou painel interativo (ID: {res.get('cmd_id')})."
            )
            return ToolResult(ok=True, message=msg, data=res)

        output = res.get("output", res.get("error", "Executado."))
        return ToolResult(ok=res.get("ok", False), message=output, data=res)
