"""API para streaming seguro de mídias locais e revelação de arquivos no Windows Explorer."""
from __future__ import annotations

import json
import mimetypes
import os
import sys
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

ALLOWED_STREAM_EXTENSIONS = frozenset({
    ".mp4", ".webm", ".mkv", ".mov", ".avi",
    ".mp3", ".wav", ".ogg", ".aac",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
})


def get_project_root() -> Path:
    """Retorna a raiz do projeto Jarvis."""
    return Path(__file__).resolve().parents[4]


def get_allowed_media_roots() -> list[Path]:
    """Retorna raízes permitidas para streaming e operações de mídia."""
    root = get_project_root()
    return [
        (root / "data" / "videos").resolve(),
        (root / "data" / "captures").resolve(),
        (root / "data").resolve(),
    ]


def validate_media_stream_path(file_param: str) -> Path:
    """Valida o caminho solicitado para streaming prevenindo directory traversal."""
    if not file_param or not str(file_param).strip():
        raise ValueError("Parâmetro 'file' não informado.")

    if "\0" in file_param:
        raise ValueError("Caractere inválido no caminho do arquivo.")

    raw_path = unquote(str(file_param).strip())
    # Normalizar separadores de caminho
    raw_path = raw_path.replace("\\", "/")

    # Rejeitar se tentar escapar com '..'
    parts = [p for p in raw_path.split("/") if p]
    if any(p == ".." for p in parts):
        raise PermissionError("Acesso negado: tentativa de directory traversal detectada.")

    root = get_project_root()
    candidate: Path | None = None

    # Tenta resolver primeiro relativo a data/videos
    videos_root = (root / "data" / "videos").resolve()
    potential = (videos_root / raw_path).resolve()
    if potential.is_relative_to(videos_root):
        candidate = potential
    else:
        # Tenta resolver relativo a data
        data_root = (root / "data").resolve()
        potential2 = (data_root / raw_path).resolve()
        if potential2.is_relative_to(data_root):
            candidate = potential2

    if candidate is None:
        raise PermissionError("Acesso negado: o arquivo solicitado está fora dos diretórios permitidos.")

    # Validar extensão permitida
    if candidate.suffix.lower() not in ALLOWED_STREAM_EXTENSIONS:
        raise PermissionError(f"Acesso negado: extensão de mídia '{candidate.suffix}' não permitida para streaming.")

    if not candidate.exists() or not candidate.is_file():
        raise FileNotFoundError(f"Arquivo de mídia não encontrado: {raw_path}")

    return candidate


def validate_reveal_path(path_param: str) -> Path:
    """Valida o caminho para revelação no Explorer prevenindo directory traversal perigoso."""
    if not path_param or not str(path_param).strip():
        raise ValueError("Parâmetro 'path' não informado.")

    if "\0" in path_param:
        raise ValueError("Caractere inválido no caminho do arquivo.")

    raw_path = str(path_param).strip().replace("\\", "/")
    parts = [p for p in raw_path.split("/") if p]
    if any(p == ".." for p in parts):
        # Se contiver '..', checamos se ao resolver escapa da raiz do projeto
        pass

    root = get_project_root()
    candidate = Path(path_param)
    if not candidate.is_absolute():
        candidate = (root / candidate).resolve()
    else:
        candidate = candidate.resolve()

    # O arquivo deve residir dentro da raiz do projeto Jarvis ou em pastas de dados permitidas
    if not candidate.is_relative_to(root):
        raise PermissionError(f"Acesso negado: caminho '{path_param}' fora do escopo do projeto.")

    if not candidate.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {path_param}")

    return candidate


def handle_media_stream(handler: Any) -> None:
    """Serve arquivo de vídeo/áudio local com cabeçalhos de streaming (Range requests)."""
    raw_query = urlsplit(getattr(handler, "path", "")).query
    query = parse_qs(raw_query)
    file_param = query.get("file", [""])[0]

    try:
        media_file = validate_media_stream_path(file_param)
    except PermissionError as exc:
        handler._send_json(403, {"ok": False, "error": str(exc)})
        return
    except ValueError as exc:
        handler._send_json(400, {"ok": False, "error": str(exc)})
        return
    except FileNotFoundError as exc:
        handler._send_json(404, {"ok": False, "error": str(exc)})
        return

    try:
        total_size = media_file.stat().st_size
        mime, _ = mimetypes.guess_type(str(media_file))
        mime = mime or "video/mp4"

        range_header = handler.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            range_val = range_header[6:].strip()
            parts = range_val.split("-")
            try:
                start = int(parts[0]) if parts[0] else 0
                end = int(parts[1]) if len(parts) > 1 and parts[1] else total_size - 1
            except ValueError:
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{total_size}")
                handler.end_headers()
                return

            if start >= total_size or end >= total_size or start > end:
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{total_size}")
                handler.end_headers()
                return

            length = end - start + 1
            handler.send_response(206)
            handler.send_header("Content-Type", mime)
            handler.send_header("Content-Range", f"bytes {start}-{end}/{total_size}")
            handler.send_header("Content-Length", str(length))
            handler.send_header("Accept-Ranges", "bytes")
            handler.send_header("Cache-Control", "no-cache")
            handler._send_cors()
            handler.end_headers()

            chunk_size = 64 * 1024
            with open(media_file, "rb") as f:
                f.seek(start)
                remaining = length
                while remaining > 0:
                    read_size = min(chunk_size, remaining)
                    data = f.read(read_size)
                    if not data:
                        break
                    handler.wfile.write(data)
                    remaining -= len(data)
            return

        # Sem cabeçalho Range: serve o arquivo completo com suporte anunciado a bytes
        handler.send_response(200)
        handler.send_header("Content-Type", mime)
        handler.send_header("Content-Length", str(total_size))
        handler.send_header("Accept-Ranges", "bytes")
        handler.send_header("Cache-Control", "no-cache")
        handler._send_cors()
        handler.end_headers()

        chunk_size = 64 * 1024
        with open(media_file, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                handler.wfile.write(data)
    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
        pass


def handle_media_reveal(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Abre e seleciona o arquivo no Windows Explorer de forma segura."""
    if path != "/api/media/reveal":
        return None

    try:
        data = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}

    file_path = str(data.get("path", "") or "").strip()
    if not file_path:
        return 400, {"ok": False, "error": "Campo 'path' é obrigatório."}

    try:
        safe_path = validate_reveal_path(file_path)
    except PermissionError as exc:
        return 403, {"ok": False, "error": str(exc)}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    except FileNotFoundError as exc:
        return 404, {"ok": False, "error": str(exc)}

    try:
        if sys.platform == "win32":
            subprocess.Popen(["explorer.exe", f"/select,{safe_path}"])
        return 200, {
            "ok": True,
            "message": "Arquivo revelado no Explorer.",
            "path": str(safe_path),
        }
    except Exception as exc:
        return 500, {"ok": False, "error": f"Falha ao executar o Explorer: {exc}"}


def handle_media_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Trata requisições GET para /api/media/* quando roteadas pelo loop de handlers."""
    if len(parts) >= 3 and parts[:2] == ["api", "media"]:
        if parts[2] == "stream":
            handle_media_stream(handler)
            return None
    return None


def handle_media_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    """Trata requisições POST para /api/media/* quando roteadas pelo loop de handlers."""
    if path == "/api/media/reveal":
        return handle_media_reveal(path, body, handler)
    return None
