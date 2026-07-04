from __future__ import annotations

from pathlib import Path
from typing import Any


class FileActionService:
    """Serve as a small action layer for file and folder operations."""

    def __init__(self, base_folder: str | None = None) -> None:
        self.base_folder = Path(base_folder or Path.cwd()).expanduser().resolve()

    def _resolve_path(self, relative_path: str = "") -> Path:
        candidate = (self.base_folder / relative_path).resolve()
        if not str(candidate).startswith(str(self.base_folder)):
            raise ValueError("Acesso a caminho fora do diretório base não permitido.")
        return candidate

    def _extract_path(self, request: str) -> str:
        normalized = (request or "").strip().lower()
        for marker in ("pasta ", "folder ", "diretório ", "diretoria "):
            if marker in normalized:
                candidate = normalized.split(marker, 1)[1].strip()
                if candidate:
                    return candidate.split()[0]
        return ""

    def execute(self, request: str) -> dict[str, Any]:
        path_fragment = self._extract_path(request)
        target_path = self._resolve_path(path_fragment)

        if not target_path.exists() or not target_path.is_dir():
            raise FileNotFoundError(f"Diretório não encontrado: {target_path}")

        items = [item.name for item in sorted(target_path.iterdir(), key=lambda entry: (not entry.is_dir(), entry.name.lower()))]
        return {
            "kind": "directory",
            "path": str(target_path.relative_to(self.base_folder)) if target_path != self.base_folder else ".",
            "items": items,
        }
