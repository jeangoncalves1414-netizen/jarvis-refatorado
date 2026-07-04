from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence


class FileManagerService:
    def __init__(self, base_folder: str | None = None) -> None:
        self.base_folder = Path(base_folder or Path.cwd()).expanduser().resolve()

    def list_directory(self, relative_path: str = "") -> list[str]:
        path = (self.base_folder / relative_path).resolve()
        if not str(path).startswith(str(self.base_folder)):
            raise ValueError("Acesso a caminho fora do diretório base não permitido.")
        if not path.exists() or not path.is_dir():
            raise FileNotFoundError(f"Diretório não encontrado: {path}")
        return [item.name for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))]

    def read_file(self, relative_path: str) -> str:
        path = (self.base_folder / relative_path).resolve()
        if not str(path).startswith(str(self.base_folder)):
            raise ValueError("Acesso a caminho fora do diretório base não permitido.")
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"Arquivo não encontrado: {path}")
        return path.read_text(encoding="utf-8", errors="replace")

    def get_supported_directories(self) -> Sequence[str]:
        return [str(self.base_folder)]
