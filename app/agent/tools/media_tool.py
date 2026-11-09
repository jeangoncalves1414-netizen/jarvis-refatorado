"""Ferramenta de mídia e vídeos locais do Jarvis com suporte a vídeos motivacionais e visualização no Windows Explorer."""
from __future__ import annotations

import json
import os
import random
import sys
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .base import BaseTool, ToolResult

ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".webm", ".mkv"})


def get_project_root() -> Path:
    """Retorna a raiz do projeto Jarvis."""
    return Path(__file__).resolve().parents[3]


def get_motivational_videos_dir(base_folder: str | Path | None = None) -> Path:
    """Retorna o diretório dedicado a vídeos motivacionais locais."""
    if base_folder is not None:
        p = Path(base_folder).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p
    root = get_project_root()
    folder = root / "data" / "videos" / "motivacionais"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def validate_safe_path(path_str: str, allowed_roots: list[Path] | None = None) -> Path:
    """Valida se o caminho é seguro e não escapa via directory traversal."""
    if not path_str or not str(path_str).strip():
        raise ValueError("Caminho não informado.")

    if "\0" in str(path_str):
        raise ValueError("Caminho inválido (caractere nulo).")

    candidate = Path(path_str)
    root = get_project_root()
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    if allowed_roots is None:
        allowed_roots = [root]

    is_safe = False
    for allowed_root in allowed_roots:
        resolved_root = allowed_root.resolve()
        try:
            if candidate.is_relative_to(resolved_root):
                is_safe = True
                break
        except (ValueError, TypeError):
            continue

    if not is_safe:
        raise PermissionError(f"Acesso negado: o caminho '{path_str}' está fora dos diretórios autorizados.")

    return candidate


class MediaTool(BaseTool):
    def __init__(self, base_folder: str | Path | None = None) -> None:
        self.base_folder = Path(base_folder).resolve() if base_folder else None

    @property
    def name(self) -> str:
        return "media_tool"

    @property
    def description(self) -> str:
        return (
            "Gerencia e reproduz mídias e vídeos locais, incluindo vídeos motivacionais na pasta dedicada "
            "e revelação de arquivos no Windows Explorer."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list_videos", "play_motivational", "reveal_in_folder"],
                    "description": (
                        "Ação a realizar: 'list_videos' para listar vídeos disponíveis, "
                        "'play_motivational' para selecionar e reproduzir um vídeo motivacional, "
                        "ou 'reveal_in_folder' para abrir o Windows Explorer selecionando o arquivo."
                    ),
                },
                "query": {
                    "type": "string",
                    "description": "Palavra-chave opcional para filtrar vídeos por título/nome.",
                },
                "path": {
                    "type": "string",
                    "description": "Caminho do arquivo para reveal_in_folder ou pasta customizada para list_videos.",
                },
            },
            "required": ["action"],
        }

    def execute(self, args: dict[str, Any], context: dict[str, Any] | None = None) -> ToolResult:
        action = str(args.get("action", "") or "").strip()
        if not action:
            return ToolResult(ok=False, message="Ação é obrigatória.")

        query = str(args.get("query", "") or "").strip()
        path_arg = str(args.get("path", "") or "").strip()

        if action == "list_videos":
            return self._list_videos(query=query, custom_path=path_arg)
        elif action == "play_motivational":
            return self._play_motivational(query=query)
        elif action == "reveal_in_folder":
            return self._reveal_in_folder(path_arg=path_arg)
        else:
            return ToolResult(ok=False, message=f"Ação desconhecida: '{action}'.")

    def _list_videos(self, query: str = "", custom_path: str = "") -> ToolResult:
        try:
            if custom_path:
                target_dir = validate_safe_path(custom_path)
            else:
                target_dir = get_motivational_videos_dir(self.base_folder)
        except (PermissionError, ValueError) as exc:
            return ToolResult(ok=False, message=f"Erro de segurança: {exc}")

        if not target_dir.exists() or not target_dir.is_dir():
            return ToolResult(ok=False, message=f"Diretório não encontrado: {target_dir}")

        videos = []
        project_root = get_project_root()
        for entry in sorted(target_dir.iterdir(), key=lambda p: p.name.lower()):
            if entry.is_file() and entry.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                if not query or query.lower() in entry.name.lower():
                    try:
                        rel_path = str(entry.relative_to(project_root)).replace("\\", "/")
                    except ValueError:
                        rel_path = entry.name
                    videos.append({
                        "name": entry.name,
                        "stem": entry.stem,
                        "path": str(entry.resolve()),
                        "relative_path": rel_path,
                        "size_bytes": entry.stat().st_size,
                    })

        if not videos:
            msg = (
                f"Nenhum vídeo encontrado com o critério '{query}'."
                if query
                else "Nenhum arquivo de vídeo encontrado na pasta de vídeos."
            )
            return ToolResult(ok=True, message=msg, data={"videos": [], "count": 0})

        lines = [f"Encontrado(s) {len(videos)} vídeo(s):"]
        for idx, v in enumerate(videos, 1):
            lines.append(f"{idx}. {v['name']} ({v['size_bytes'] / (1024 * 1024):.1f} MB)")

        return ToolResult(
            ok=True,
            message="\n".join(lines),
            data={"videos": videos, "count": len(videos)},
        )

    def _play_motivational(self, query: str = "") -> ToolResult:
        target_dir = get_motivational_videos_dir(self.base_folder)
        candidates: list[Path] = []
        for entry in target_dir.iterdir():
            if entry.is_file() and entry.suffix.lower() in ALLOWED_VIDEO_EXTENSIONS:
                if not query or query.lower() in entry.name.lower():
                    candidates.append(entry)

        if not candidates:
            return ToolResult(
                ok=False,
                message=(
                    f"Nenhum vídeo motivacional encontrado para '{query}'."
                    if query
                    else "Nenhum vídeo motivacional encontrado em 'data/videos/motivacionais'."
                ),
                data={"videos": []},
            )

        chosen = random.choice(candidates)
        root = get_project_root()
        data_videos = (root / "data" / "videos").resolve()

        try:
            rel_to_videos = str(chosen.resolve().relative_to(data_videos)).replace("\\", "/")
        except ValueError:
            rel_to_videos = f"motivacionais/{chosen.name}"

        stream_url = f"/api/media/stream?file={quote(rel_to_videos)}"
        title = chosen.stem.replace("_", " ").replace("-", " ").strip().title()

        payload = {
            "type": "video",
            "url": stream_url,
            "path": str(chosen.resolve()),
            "title": title,
        }

        marker = f"__MEDIA_VIEW__{json.dumps(payload, ensure_ascii=False)}"
        message = f"Reproduzindo vídeo motivacional: {title}\n{marker}"

        return ToolResult(
            ok=True,
            message=message,
            data=payload,
        )

    def _reveal_in_folder(self, path_arg: str) -> ToolResult:
        if not path_arg:
            return ToolResult(ok=False, message="Caminho do arquivo não fornecido para revelação no Explorer.")

        try:
            safe_path = validate_safe_path(path_arg)
        except PermissionError as exc:
            return ToolResult(ok=False, message=f"Erro de segurança: {exc}")
        except ValueError as exc:
            return ToolResult(ok=False, message=f"Caminho inválido: {exc}")

        if not safe_path.exists():
            return ToolResult(ok=False, message=f"Arquivo não encontrado: {path_arg}")

        try:
            if sys.platform == "win32":
                subprocess.Popen(["explorer.exe", f"/select,{safe_path}"])
            return ToolResult(
                ok=True,
                message=f"Arquivo selecionado no Windows Explorer: {safe_path.name}",
                data={"path": str(safe_path)},
            )
        except Exception as exc:
            return ToolResult(ok=False, message=f"Falha ao executar Explorer: {exc}")
