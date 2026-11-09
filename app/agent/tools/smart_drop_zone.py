"""Smart Drop Zone Tool (inspirado no IRIS-AI).

Organiza autonomamente a pasta Downloads ou Área de Trabalho movendo arquivos
para subpastas categorizadas (Documentos, Imagens, Códigos, Compactados, Executáveis).
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any
from app.agent.tools.base import BaseTool

RULE_CATEGORIES = {
    "Documentos": {".pdf", ".docx", ".doc", ".xlsx", ".pptx", ".txt", ".csv"},
    "Imagens": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg", ".bmp"},
    "Compactados": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Executaveis": {".exe", ".msi", ".bat", ".cmd", ".ps1"},
    "Codigos": {".py", ".ts", ".tsx", ".js", ".html", ".css", ".java", ".kt", ".c", ".cpp"}
}


class SmartDropZoneTool(BaseTool):
    name = "smart_drop_zone"
    description = "Organiza autonomamente a pasta Downloads ou Área de Trabalho por categorias de arquivo."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "target_folder": {"type": "string", "enum": ["Downloads", "Desktop"], "description": "Pasta a organizar (padrão Downloads)."},
            },
        }

    def run(self, target_folder: str = "Downloads", **kwargs: Any) -> dict[str, Any]:
        target_folder = target_folder.strip().lower()
        home = Path.home()
        
        if "desktop" in target_folder:
            source_dir = home / "Desktop"
        else:
            source_dir = home / "Downloads"

        if not source_dir.exists():
            return {"success": False, "error": f"Diretório {source_dir} não existe."}

        moved_count = 0
        details: list[dict[str, str]] = []

        for item in source_dir.iterdir():
            if item.is_dir() or item.name.startswith("."):
                continue

            ext = item.suffix.lower()
            dest_category = None

            for cat_name, exts in RULE_CATEGORIES.items():
                if ext in exts:
                    dest_category = cat_name
                    break

            if dest_category:
                dest_dir = source_dir / dest_category
                dest_dir.mkdir(exist_ok=True)
                dest_file = dest_dir / item.name
                
                try:
                    shutil.move(str(item), str(dest_file))
                    moved_count += 1
                    details.append({"file": item.name, "category": dest_category})
                except Exception as e:
                    continue

        return {
            "success": True,
            "target": str(source_dir),
            "moved_count": moved_count,
            "details": details
        }
