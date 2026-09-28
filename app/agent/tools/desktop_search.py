"""Desktop File Search Tool (inspirado no Brahma-AI e IRIS-AI).

Permite busca indexada rápida de arquivos na Área de Trabalho, Downloads, Documentos
e projetos do usuário por categoria (código, documento, imagem, áudio) e filtros temporais.
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any
from app.agent.tools.base import BaseTool

HOME_DIR = Path.home()
# Pasta do projeto Jarvis (detectada dinamicamente a partir do local do módulo)
_PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
SEARCH_LOCATIONS = [
    HOME_DIR / "Desktop",
    HOME_DIR / "Downloads",
    HOME_DIR / "Documents",
    _PROJECT_DIR,
]

CATEGORIES = {
    "code": {".py", ".ts", ".tsx", ".js", ".json", ".html", ".css", ".java", ".kt", ".c", ".cpp"},
    "document": {".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md", ".csv"},
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"},
    "archive": {".zip", ".rar", ".7z", ".tar", ".gz"}
}

# Resource limits for security
MAX_QUERY_LENGTH = 200
MAX_TERM_LENGTH = 50
MAX_QUERY_TERMS = 10
MAX_RESULTS_LIMIT = 100
MAX_DEPTH = 5
MAX_FILES_PER_DIR = 100
SEARCH_TIMEOUT = 10  # seconds


class DesktopSearchTool(BaseTool):
    name = "desktop_search"
    description = "Busca arquivos no computador (Desktop, Downloads, Documentos) por palavra-chave, extensão e intervalo de tempo."

    def _validate_search_location(self, path: Path) -> bool:
        """Ensure search location is safe and accessible."""
        try:
            # Check if path is within user home or project dir
            if not (path.is_relative_to(HOME_DIR) or path.is_relative_to(_PROJECT_DIR)):
                return False
            
            # Check if path exists and is readable
            if not path.exists() or not path.is_dir():
                return False
            
            return True
        except (OSError, PermissionError):
            return False

    def run(
        self,
        query: str = "",
        category: str = "",
        max_results: int = 15,
        **kwargs: Any
    ) -> dict[str, Any]:
        # Validate query length and content
        if len(query) > MAX_QUERY_LENGTH:
            return {"success": False, "error": f"Query too long (max {MAX_QUERY_LENGTH} characters)"}
        
        # Validate max_results
        if not (1 <= max_results <= MAX_RESULTS_LIMIT):
            return {"success": False, "error": f"max_results must be between 1 and {MAX_RESULTS_LIMIT}"}
        
        # Sanitize query terms
        query_terms = [q.lower() for q in query.strip().split() if len(q) >= 2 and len(q) <= MAX_TERM_LENGTH]
        if len(query_terms) > MAX_QUERY_TERMS:
            return {"success": False, "error": f"Too many search terms (max {MAX_QUERY_TERMS})"}
        
        # Validate category
        category = category.lower().strip()
        if category and category not in CATEGORIES:
            return {"success": False, "error": f"Invalid category: {category}"}
        
        allowed_exts = CATEGORIES.get(category, set())

        matches: list[dict[str, Any]] = []
        start_time = time.time()

        for base_path in SEARCH_LOCATIONS:
            # Check timeout
            if time.time() - start_time > SEARCH_TIMEOUT:
                break
            
            # Validate search location
            if not self._validate_search_location(base_path):
                continue
            
            try:
                for root, dirs, files in os.walk(base_path):
                    # Check timeout
                    if time.time() - start_time > SEARCH_TIMEOUT:
                        break
                    
                    # Check depth limit
                    rel_depth = len(Path(root).relative_to(base_path).parts)
                    if rel_depth > MAX_DEPTH:
                        dirs[:] = []  # Don't descend further
                        continue
                    
                    # Limit files per directory
                    if len(files) > MAX_FILES_PER_DIR:
                        files = files[:MAX_FILES_PER_DIR]
                    
                    # Ignorar pastas de sistema/dependências para velocidade
                    if any(skip in root for skip in (".git", "node_modules", ".venv", "__pycache__", ".gradle")):
                        continue

                    for file in files:
                        filepath = Path(root) / file
                        file_lower = file.lower()

                        # Filtro por extensão de categoria se especificado
                        if allowed_exts and filepath.suffix.lower() not in allowed_exts:
                            continue

                        # Filtro por termos de pesquisa
                        if query_terms and not any(term in file_lower for term in query_terms):
                            continue

                        try:
                            stat = filepath.stat()
                            matches.append({
                                "name": file,
                                "path": str(filepath),
                                "size_bytes": stat.st_size,
                                "modified_time": time.ctime(stat.st_mtime),
                                "ext": filepath.suffix
                            })
                        except OSError:
                            continue

                        if len(matches) >= max_results:
                            break
                    if len(matches) >= max_results:
                        break
            except Exception:
                continue

        return {
            "success": True,
            "query": query,
            "category": category,
            "count": len(matches),
            "results": matches
        }
