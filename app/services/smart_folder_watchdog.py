"""
Smart Folder Watchdog — inspirado no IRIS-AI
Organiza autonomamente a pasta 'Downloads' ou diretórios selecionados por regras de tipo de arquivo.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any


class SmartFolderWatchdog:
    """Organizador autônomo de pastas."""

    CATEGORIES = {
        "Documentos": [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv"],
        "Imagens": [".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"],
        "Executáveis": [".exe", ".msi", ".apk"],
        "Compactados": [".zip", ".rar", ".7z", ".tar", ".gz"],
        "Código": [".py", ".ts", ".tsx", ".js", ".html", ".css", ".json"],
    }

    @classmethod
    def organize_directory(cls, dir_path: str = "~/Downloads") -> dict[str, Any]:
        target = Path(dir_path).expanduser().resolve()
        if not target.exists() or not target.is_dir():
            return {"ok": False, "error": f"Diretório '{dir_path}' não encontrado."}

        moved_count = 0
        details = []

        for item in target.iterdir():
            if item.is_file() and not item.name.startswith("."):
                ext = item.suffix.lower()
                for cat_name, extensions in cls.CATEGORIES.items():
                    if ext in extensions:
                        dest_folder = target / cat_name
                        dest_folder.mkdir(exist_ok=True)
                        dest_file = dest_folder / item.name
                        try:
                            shutil.move(str(item), str(dest_file))
                            moved_count += 1
                            details.append(f"{item.name} ➔ {cat_name}")
                        except Exception:
                            pass
                        break

        return {
            "ok": True,
            "moved_count": moved_count,
            "details": details,
            "message": f"Organização concluída: {moved_count} arquivos movidos em '{target.name}'.",
        }
