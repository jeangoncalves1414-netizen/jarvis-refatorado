"""ScreenPeeler Tool (inspirado no IRIS-AI).

Captura a tela ou região selecionada, realiza OCR com visão multimodal (Gemini/Groq)
e copia automaticamente o resultado limpo para a área de transferência do Windows.
"""
from __future__ import annotations

import io
from typing import Any

from app.agent.tools.base import BaseTool


class ScreenPeelerTool(BaseTool):
    name = "screen_peeler"
    description = "Captura a tela atual, realiza OCR inteligente com IA e envia o texto extraído para a área de transferência."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {"type": "string", "description": "Instrução de extração (padrão: extrair todo o texto visível)."},
            },
        }

    def run(self, prompt: str = "Extraia todo o texto visível nesta imagem de tela.", **kwargs: Any) -> dict[str, Any]:
        try:
            # Importações opcionais — não falham em tempo de import
            try:
                import pyperclip
            except ImportError:
                pyperclip = None  # type: ignore[assignment]

            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab()
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")
                image_bytes = buffer.getvalue()
            except Exception as cap_err:
                return {"success": False, "error": f"Falha ao capturar tela: {cap_err}"}

            # Usa VisionService via contexto do agente (se disponível)
            vision = kwargs.get("vision")
            if vision is None:
                try:
                    from app.services.vision import VisionService
                    vision = VisionService()
                except Exception:
                    vision = None

            if vision is not None:
                extracted_text = vision.analyze_bytes(prompt, image_bytes)
            else:
                extracted_text = "[Serviço de visão não disponível. Configure uma chave de API para OCR.]"

            clean_text = (extracted_text or "").strip()

            if clean_text and pyperclip:
                pyperclip.copy(clean_text)

            return {
                "success": True,
                "text_copied": bool(clean_text and pyperclip),
                "extracted_text": clean_text
            }
        except Exception as e:
            return {"success": False, "error": f"Falha no ScreenPeeler: {e}"}
