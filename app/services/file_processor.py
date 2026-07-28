from __future__ import annotations

import shutil
from pathlib import Path
from typing import List


class FileProcessor:
    """Operações avançadas de arquivos."""
    
    @staticmethod
    def batch_move(src_patterns: List[str], dst: Path, base_dir: Path | None = None) -> dict[str, bool]:
        """Move arquivos por padrão."""
        results = {}
        base = base_dir or Path(".")
        for pattern in src_patterns:
            for src in base.glob(pattern):
                try:
                    shutil.move(str(src), str(dst))
                    results[str(src)] = True
                except Exception:
                    results[str(src)] = False
        return results
    
    @staticmethod
    def batch_copy(src_patterns: List[str], dst: Path, base_dir: Path | None = None) -> dict[str, bool]:
        """Copia arquivos por padrão."""
        results = {}
        base = base_dir or Path(".")
        for pattern in src_patterns:
            for src in base.glob(pattern):
                try:
                    shutil.copy2(str(src), str(dst))
                    results[str(src)] = True
                except Exception:
                    results[str(src)] = False
        return results
    
    @staticmethod
    def get_metadata(path: Path) -> dict:
        """Retorna metadados de arquivo."""
        stat = path.stat()
        return {
            "size": stat.st_size,
            "modified": stat.st_mtime,
            "created": stat.st_ctime,
            "extension": path.suffix
        }
