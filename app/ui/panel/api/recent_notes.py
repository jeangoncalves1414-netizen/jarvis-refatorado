"""Consulta de anotações pessoais para o cartão Hoje."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


def _note_file(root: Path, relative: str, folders: tuple[str, ...]) -> Path:
    parts = relative.split("/")
    if len(parts) != 2 or parts[0] not in folders or not re.fullmatch(r"[^/\\:\x00-\x1f]+\.md", parts[1], re.I):
        raise ValueError("Anotação inválida.")
    path = root / relative
    if path.resolve() != root.resolve() / relative:
        raise ValueError("Anotação fora da pasta permitida.")
    return path


def recent_notes(root: Path, folders: tuple[str, ...]) -> list[dict[str, Any]]:
    files = []
    for folder in folders:
        for candidate in (root / folder).glob("*.md"):
            relative = f"{folder}/{candidate.name}"
            try:
                path = _note_file(root, relative, folders)
                if path.is_file():
                    files.append((path.stat().st_mtime, relative, path))
            except (FileNotFoundError, ValueError):
                continue
    items = []
    for modified, relative, path in sorted(files, reverse=True):
        try:
            with path.open(encoding="utf-8-sig") as stream:
                # Arquivos de priming instalados pelo sistema não são capturas pessoais.
                heading = stream.readline(512).strip()
                if relative.startswith("03-Priming-Notes/") and relative.split("/")[1] in {"analysis.md", "writing.md", "coding.md"} and heading.startswith("# ") and "Priming" in heading:
                    continue
                if relative.startswith("01-Daily-Notes/") and heading.startswith("# 📅 Diário de Sessão") and not any(line.startswith("- ") for line in stream):
                    continue
        except (FileNotFoundError, UnicodeError):
            continue
        title = heading.removeprefix("# ").strip() if heading.startswith("# ") else path.stem
        items.append({"path": relative, "title": title, "modified": int(modified * 1000)})
        if len(items) == 12:
            break
    return items


def handle_recent_notes_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if parts not in (["api", "notes", "recent"], ["api", "notes", "read"]):
        return None
    from app.agent.tools.memory_vault_tool import NOTE_FOLDERS
    from app.services.memory_vault import VAULT_DIR

    try:
        if parts[-1] == "recent":
            return 200, {"ok": True, "notes": recent_notes(VAULT_DIR, NOTE_FOLDERS)}
        relative = parse_qs(urlsplit(handler.path).query).get("path", [""])[0]
        path = _note_file(VAULT_DIR, relative, NOTE_FOLDERS)
        return 200, {"ok": True, "content": path.read_text(encoding="utf-8-sig")}
    except ValueError:
        return 400, {"ok": False, "error": "A anotação solicitada é inválida."}
    except FileNotFoundError:
        return 404, {"ok": False, "error": "Esta anotação já não está no cofre."}
    except OSError:
        return 500, {"ok": False, "error": "Não foi possível ler o cofre agora."}
