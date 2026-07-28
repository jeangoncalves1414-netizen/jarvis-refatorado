from __future__ import annotations

import csv
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolResult

# Anti-spam/anti-loop globals
_last_sent_time: dict[str, float] = {}
_last_sent_msg: dict[str, str] = {}


class WhatsAppTool(BaseTool):
    @property
    def name(self) -> str:
        return "whatsapp"

    @property
    def description(self) -> str:
        return "Envia mensagens via WhatsApp (usando Mudslide) para contatos ou números específicos."

    @property
    def critical(self) -> bool:
        return True

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "description": "Nome do contato (do CSV) ou número de telefone direto."
                },
                "message": {
                    "type": "string",
                    "description": "Mensagem de texto a ser enviada."
                }
            },
            "required": ["target", "message"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        target = args.get("target", "").strip()
        message = args.get("message", "").strip()

        if not target or not message:
            return ToolResult(ok=False, message="Destinatário e mensagem são obrigatórios.")

        phone = self._resolve_contact(target)
        if not phone:
            return ToolResult(
                ok=False,
                message=f"Não foi possível resolver o contato '{target}'. "
                        f"Insira o número de telefone completo ou cadastre o contato em 'data/contatos.csv'."
            )

        # Adiciona prefixo +55 se for número brasileiro padrão sem DDI
        if len(phone) >= 10 and not phone.startswith("+"):
            phone = "+55" + phone

        # Anti-spam e anti-loop
        now = time.time()
        if phone in _last_sent_time:
            time_diff = now - _last_sent_time[phone]
            if time_diff < 10:
                return ToolResult(ok=False, message="ANTI-SPAM: Aguarde 10 segundos antes de enviar outra mensagem para este número.")
            if _last_sent_msg.get(phone) == message and time_diff < 300:
                return ToolResult(ok=False, message="ANTI-LOOP: Mensagem duplicada detectada para este número nos últimos 5 minutos.")

        # Executa mudslide
        try:
            is_win = os.name == "nt"
            # No Windows, chama npx através de shell=True para invocar o npx.cmd correto
            cmd = ["npx", "mudslide", "send", phone, message]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=is_win,
                creationflags=0x08000000 if is_win else 0
            )

            if result.returncode == 0:
                _last_sent_time[phone] = now
                _last_sent_msg[phone] = message
                return ToolResult(ok=True, message=f"Mensagem enviada com sucesso para {target} ({phone}).")
            else:
                stderr = result.stderr.lower()
                stdout = result.stdout.lower()
                if "login" in stderr or "login" in stdout:
                    return ToolResult(
                        ok=False,
                        message="WhatsApp desconectado. Por favor, execute 'npx mudslide login' no terminal para parear o QR Code."
                    )
                return ToolResult(ok=False, message=f"Erro do Mudslide: {result.stderr or result.stdout}")

        except Exception as e:
            return ToolResult(ok=False, message=f"Erro ao disparar Mudslide: {e}")

    def _resolve_contact(self, name_or_phone: str) -> str:
        cleaned = "".join(c for c in name_or_phone if c.isdigit() or c == "+")
        if len(cleaned) >= 8:
            return cleaned

        csv_path = Path("data/contatos.csv")
        if not csv_path.exists():
            return ""

        query = name_or_phone.strip().lower()
        try:
            with open(csv_path, mode="r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                for row in reader:
                    row_text = " ".join(row[:5]).lower()
                    if query in row_text:
                        nums = ["".join(c for c in cell if c.isdigit() or c == "+") for cell in row]
                        valid = [n for n in nums if len(n) >= 8]
                        if valid:
                            return valid[0]
        except Exception:
            pass
        return ""
