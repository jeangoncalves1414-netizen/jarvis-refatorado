"""Phantom Typer Tool (inspirado no IRIS-AI).

Digita textos longos, trechos de código ou respostas diretamente no aplicativo/editor
ativo no Windows simulando pressionamento autônomo de teclas.
"""
from __future__ import annotations

import time
from typing import Any
from app.agent.tools.base import BaseTool


class PhantomTyperTool(BaseTool):
    name = "phantom_typer"
    description = "Digita autonomamente um texto ou trecho de código na janela ativa do Windows onde o cursor estiver posicionado."

    def run(self, text: str = "", delay_seconds: float = 1.0, **kwargs: Any) -> dict[str, Any]:
        if not text:
            return {"success": False, "error": "Nenhum texto informado para digitação."}

        time.sleep(max(0.5, float(delay_seconds)))

        try:
            import pyperclip  # pylint: disable=import-outside-toplevel
            import pyautogui  # pylint: disable=import-outside-toplevel
            # Para manter suporte a caracteres com acentuação e Unicode no Windows,
            # usamos a injeção via Clipboard + Ctrl+V com segurança
            original_clip = pyperclip.paste()
            pyperclip.copy(text)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.2)
            pyperclip.copy(original_clip)

            return {
                "success": True,
                "typed_length": len(text)
            }
        except Exception as e:
            return {"success": False, "error": f"Falha na injeção do Phantom Typer: {e}"}
