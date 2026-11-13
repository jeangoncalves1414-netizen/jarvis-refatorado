from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
from .base import BaseTool, ToolResult
from app.services.vision import VisionService, VISION_AVAILABLE


class VisionTool(BaseTool):
    """Ferramenta de visão para capturar e analisar tela ou câmera do usuário."""

    @property
    def name(self) -> str:
        return "vision"

    @property
    def description(self) -> str:
        return (
            "Captura e analisa a tela atual ou a webcam do usuário usando visão computacional (multimodal). "
            "Use quando o usuário pedir para ver a tela, tirar print, analisar código/erro visível, "
            "ou tirar foto da câmera."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["analyze_screen", "analyze_camera"],
                    "description": "Ação de visão: 'analyze_screen' para capturar e analisar a tela; 'analyze_camera' para webcam."
                },
                "prompt": {
                    "type": "string",
                    "description": "A instrução ou pergunta sobre o que analisar na imagem (ex: 'O que está errado neste código na tela?')."
                }
            },
            "required": ["action"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "analyze_screen")).lower()
        if action not in {"analyze_screen", "analyze_camera"}:
            return ToolResult(False, "Ação de visão inválida. Use analyze_screen ou analyze_camera.")
        # The React camera workspace owns device selection and consent.  The
        # assistant must not silently open the operating-system default camera.
        if action == "analyze_camera":
            return ToolResult(
                ok=False,
                message="Abra o Espaço de Câmeras, selecione a transmissão desejada e faça a pergunta por lá.",
            )
        if not VISION_AVAILABLE:
            return ToolResult(ok=False, message="Visão computacional indisponível (dependências mss/Pillow ausentes).")
        prompt = str(args.get("prompt", "Descreva detalhadamente o conteúdo desta imagem.")).strip()

        try:
            service = VisionService.from_settings((context or {}).get("settings"))
            image = service.capture_pil()
            if image is None:
                return ToolResult(False, "Não foi possível capturar a tela; nenhuma observação visual foi feita.")
            captured_at = datetime.now(timezone.utc).isoformat()
            res = service.analyze(prompt=prompt, image=image)

            reply = res.get("reply", "Sem resposta.")
            filename = res.get("capture_filename", "")
            return ToolResult(
                ok=res.get("ok", False),
                message=(f"[Observação da tela em {captured_at}; imagem única: {filename}; "
                         f"provedor: {res.get('provider') or 'não informado'}; "
                         f"modelo: {res.get('model') or 'não informado'}]\n{reply}"),
                data={"capture_filename": filename, "reply": reply, "captured_at": captured_at, "source": "screen",
                      "provider": res.get("provider"), "model": res.get("model")}
            )
        except Exception as exc:
            return ToolResult(ok=False, message=f"Falha na execução da ferramenta de visão: {exc}")
