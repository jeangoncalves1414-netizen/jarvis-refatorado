"""
AI Wallpaper Engine Tool — Troca o plano de fundo (papel de parede) do Windows por linguagem natural.
Baixa imagens de alta resolução baseadas no tema ou gera gradientes futuristas.
"""
from __future__ import annotations

import ctypes
import os
import urllib.request
from pathlib import Path
from typing import Any
from .base import BaseTool, ToolResult

WALLPAPER_DIR = Path("data/wallpapers")


def set_windows_wallpaper(image_path: str) -> bool:
    """Altera o papel de parede do Windows usando a API Win32 SystemParametersInfoW."""
    try:
        # SPI_SETDESKWALLPAPER = 20 (0x0014), SPIF_UPDATEINIFILE = 0x01 | SPIF_SENDCHANGE = 0x02
        abs_path = os.path.abspath(image_path)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, abs_path, 3)
        return True
    except Exception:
        return False


class WallpaperEngineTool(BaseTool):
    """Ferramenta para alterar o papel de parede do SO usando termos de busca ou geração."""

    @property
    def name(self) -> str:
        return "wallpaper_engine"

    @property
    def description(self) -> str:
        return (
            "Altera o plano de fundo (papel de parede) da área de trabalho do Windows."
            " Aceita um termo visual em linguagem natural (ex: 'cyberpunk city neon', 'nature mountain', 'space galaxy')."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Descrição visual do papel de parede desejado (ex: 'cyberpunk city neon', 'minimalist space').",
                },
                "image_url": {
                    "type": "string",
                    "description": "URL direta de uma imagem para definir como papel de parede (opcional).",
                },
            },
            "required": [],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        query = args.get("query", "futuristic sci-fi neon").strip()
        image_url = args.get("image_url", "").strip()

        WALLPAPER_DIR.mkdir(parents=True, exist_ok=True)
        file_path = WALLPAPER_DIR / "current_wallpaper.jpg"

        if image_url:
            target_url = image_url
        else:
            encoded_query = urllib.parse.quote(query)
            target_url = f"https://source.unsplash.com/1920x1080/?{encoded_query}"

        try:
            req = urllib.request.Request(
                target_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp, open(file_path, "wb") as f:
                f.write(resp.read())

            if set_windows_wallpaper(str(file_path)):
                return ToolResult(
                    ok=True,
                    message=f"🎨 Plano de fundo do Windows alterado com sucesso para o tema: '{query}'!",
                    data={"file_path": str(file_path), "query": query},
                )
            else:
                return ToolResult(ok=False, message="Erro ao chamar API do Windows (SystemParametersInfoW).")
        except Exception as e:
            # Fallback se Unsplash falhar — criar ou notificar
            return ToolResult(
                ok=False,
                message=f"Não foi possível baixar/definir a imagem para '{query}': {e}",
            )
