from __future__ import annotations

import ctypes
import os
import subprocess
import time
from typing import Any
from .base import BaseTool, ToolResult

# Windows Virtual Key Codes & constants
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_MEDIA_NEXT = 0xB0
_VK_MEDIA_PREV = 0xB1
_VK_MEDIA_STOP = 0xB2
_VK_RETURN = 0x0D
_VK_TAB = 0x09
_KEYEVENTF_EXTENDEDKEY = 0x0001
_KEYEVENTF_KEYUP = 0x0002


def _press(vk: int, extended: bool = True) -> None:
    flags = _KEYEVENTF_EXTENDEDKEY if extended else 0
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)
    ctypes.windll.user32.keybd_event(vk, 0, flags | _KEYEVENTF_KEYUP, 0)


def _get_spotify_window_title() -> str:
    titles: list[str] = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    def enum_callback(hwnd, _):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if "Spotify" in title and len(title) > 3:
                titles.append(title)
        return True

    ctypes.windll.user32.EnumWindows(enum_callback, 0)

    for t in titles:
        if " - " in t and t not in ("Spotify Free", "Spotify Premium", "Spotify"):
            return t
    return titles[0] if titles else ""


def _is_spotify_running() -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"],
            capture_output=True, text=True, timeout=5,
            creationflags=0x08000000
        )
        return "Spotify.exe" in result.stdout
    except Exception:
        return False


def _open_spotify() -> bool:
    try:
        os.startfile("spotify:")
        return True
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", "spotify"], creationflags=0x08000000)
            return True
        except Exception:
            return False


def _focus_spotify() -> bool:
    target_hwnd = None

    @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
    def enum_callback(hwnd, _):
        nonlocal target_hwnd
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buff = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value
            if "Spotify" in title and ctypes.windll.user32.IsWindowVisible(hwnd):
                target_hwnd = hwnd
                return False
        return True

    ctypes.windll.user32.EnumWindows(enum_callback, 0)

    if target_hwnd:
        if ctypes.windll.user32.IsIconic(target_hwnd):
            ctypes.windll.user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
        ctypes.windll.user32.SetForegroundWindow(target_hwnd)
        return True
    return False


class SpotifyTool(BaseTool):
    @property
    def name(self) -> str:
        return "spotify"

    @property
    def description(self) -> str:
        return "Controla o Spotify Desktop localmente para reproduzir, pausar, avançar, retroceder ou buscar músicas."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["play_pause", "next", "previous", "current_track", "search_play", "open"],
                    "description": "Ação a ser executada no Spotify."
                },
                "query": {
                    "type": "string",
                    "description": "Termo de busca (música ou artista) para a ação search_play."
                }
            },
            "required": ["action"]
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = args.get("action", "play_pause")

        if action == "play_pause":
            _press(_VK_MEDIA_PLAY_PAUSE)
            return ToolResult(ok=True, message="Play/Pause alternado no Spotify.")

        elif action == "next":
            _press(_VK_MEDIA_NEXT)
            return ToolResult(ok=True, message="Música avançada.")

        elif action == "previous":
            _press(_VK_MEDIA_PREV)
            return ToolResult(ok=True, message="Retornando para a faixa anterior.")

        elif action == "current_track":
            title = _get_spotify_window_title()
            if not title:
                if not _is_spotify_running():
                    return ToolResult(ok=False, message="O Spotify Desktop não está sendo executado.")
                return ToolResult(ok=True, message="Spotify está ativo, mas nenhuma música está sendo reproduzida.")
            return ToolResult(ok=True, message=f"Tocando agora: {title}", data={"title": title})

        elif action == "open":
            if _is_spotify_running():
                _focus_spotify()
                return ToolResult(ok=True, message="Spotify já estava aberto, focalizei a janela.")
            if _open_spotify():
                return ToolResult(ok=True, message="Spotify aberto com sucesso.")
            return ToolResult(ok=False, message="Não foi possível iniciar o Spotify. Verifique se está instalado.")

        elif action == "search_play":
            query = args.get("query", "").strip()
            if not query:
                return ToolResult(ok=False, message="Parâmetro 'query' contendo nome da música ou artista é obrigatório.")

            was_running = _is_spotify_running()
            if not was_running:
                _open_spotify()
                time.sleep(2.0)

            try:
                from urllib.parse import quote
                uri = f"spotify:search:{quote(query)}"
                os.startfile(uri)
            except Exception as e:
                return ToolResult(ok=False, message=f"Erro ao disparar URI de busca do Spotify: {e}")

            # Tempo de espera para renderização da busca
            time.sleep(5.0 if not was_running else 2.5)

            if _focus_spotify():
                time.sleep(1.5)
                # Simula navegação do teclado para iniciar o primeiro resultado
                _press(_VK_TAB)
                time.sleep(0.2)
                _press(_VK_TAB)
                time.sleep(0.2)
                _press(_VK_RETURN, extended=False)
                time.sleep(1.0)
                _press(_VK_MEDIA_PLAY_PAUSE)
                return ToolResult(ok=True, message=f"Busquei e tentei reproduzir '{query}' no Spotify.")
            
            return ToolResult(ok=True, message=f"Busca por '{query}' aberta, mas a janela do Spotify não pôde ser focalizada automaticamente.")

        return ToolResult(ok=False, message=f"Ação desconhecida: {action}")
