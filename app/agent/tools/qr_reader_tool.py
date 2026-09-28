from __future__ import annotations

from typing import Any
from .base import BaseTool, ToolResult
from app.services.qr_reader import QRReaderService, QR_AVAILABLE


class QRReaderTool(BaseTool):
    """Lê QR Codes da tela ou câmera do usuário."""

    @property
    def name(self) -> str:
        return "qr_reader"

    @property
    def description(self) -> str:
        return (
            "Lê e decodifica QR Codes. Pode capturar da tela atual do computador "
            "ou da câmera/webcam. Use quando o usuário pedir para ler um QR code, "
            "escanear QR, ou decodificar um código QR visível na tela ou câmera."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "enum": ["screen", "camera"],
                    "description": (
                        "'screen' para capturar a tela e buscar QR codes; "
                        "'camera' para abrir a webcam e escanear QR codes em tempo real."
                    ),
                },
                "monitor": {
                    "type": "integer",
                    "description": "Índice do monitor a capturar (0=todos, 1=principal, 2=secundário...). Padrão: 0.",
                },
                "camera_index": {
                    "type": "integer",
                    "description": "Índice da câmera (0=padrão, 1=segunda câmera...). Padrão: 0.",
                },
                "timeout": {
                    "type": "number",
                    "description": "Tempo máximo em segundos para escanear pela câmera. Padrão: 8 segundos.",
                },
            },
            "required": ["source"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        if not QR_AVAILABLE:
            avail = QRReaderService.availability()
            missing = [k for k, v in avail.items() if not v and k != "ready"]
            return ToolResult(
                ok=False,
                message=(
                    "⚠️ Dependências de QR não instaladas. "
                    f"Instale com: pip install pyzbar opencv-python pillow mss\n"
                    f"Status: {avail}"
                ),
            )

        source = str(args.get("source", "screen")).lower()
        svc = QRReaderService()

        if source == "screen":
            monitor = int(args.get("monitor", 0))
            result = svc.read_from_screen(monitor=monitor)
        elif source == "camera":
            cam_idx = int(args.get("camera_index", 0))
            timeout = float(args.get("timeout", 8.0))
            result = svc.read_from_camera(camera_index=cam_idx, timeout_s=timeout)
        else:
            return ToolResult(ok=False, message=f"Fonte inválida: '{source}'. Use 'screen' ou 'camera'.")

        if not result.ok:
            return ToolResult(ok=False, message=f"Erro ao ler QR: {result.error}", data=result.to_dict())

        if not result.codes:
            return ToolResult(
                ok=True,
                message=f"Nenhum QR Code encontrado na {source}. ({result.capture_time_ms:.0f}ms)",
                data=result.to_dict(),
            )

        lines = [f"✅ {len(result.codes)} QR Code(s) encontrado(s) na {source}:\n"]
        for i, code in enumerate(result.codes, 1):
            lines.append(f"**#{i} [{code['type']}]**")
            lines.append(f"Conteúdo: `{code['data']}`")
        lines.append(f"\n⏱ Tempo de captura: {result.capture_time_ms:.0f}ms")

        return ToolResult(
            ok=True,
            message="\n".join(lines),
            data=result.to_dict(),
        )
