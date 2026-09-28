"""
Code Versioning & Snapshot Rollback Manager
Cria checkpoints automáticos de arquivos do projeto antes de qualquer edição
e permite restaurar (rollback) versões anteriores caso o código editado falhe.
"""
from __future__ import annotations

import os
import shutil
import time
import hashlib
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = Path("data/snapshots")
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class SnapshotVersion:
    version_id: str
    filepath: str
    timestamp: float
    backup_path: str
    file_size: int
    hash_sha256: str
    change_summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version_id": self.version_id,
            "filepath": self.filepath,
            "timestamp": self.timestamp,
            "readable_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.timestamp)),
            "backup_path": self.backup_path,
            "file_size": self.file_size,
            "hash": self.hash_sha256[:12],
            "change_summary": self.change_summary,
        }


class CodeSnapshotManager:
    """Gerencia backups automáticos de arquivos e rollback de versões."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.storage_dir = base_dir or SNAPSHOTS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_file = self.storage_dir / "manifest.json"
        self._manifest: dict[str, list[dict[str, Any]]] = self._load_manifest()

    def _load_manifest(self) -> dict[str, list[dict[str, Any]]]:
        if self._manifest_file.exists():
            try:
                with open(self._manifest_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_manifest(self) -> None:
        try:
            with open(self._manifest_file, "w", encoding="utf-8") as f:
                json.dump(self._manifest, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.error("Erro ao salvar manifesto de snapshots: %s", exc)

    def _file_hash(self, content: bytes) -> str:
        return hashlib.sha256(content).hexdigest()

    def create_snapshot(self, filepath: str, summary: str = "Backup automático pré-edição") -> SnapshotVersion | None:
        """
        Cria um checkpoint/snapshot do arquivo antes de ser modificado.
        Retorna a nova versão gravada.
        """
        path = Path(filepath)
        if not path.exists() or not path.is_file():
            return None

        try:
            content = path.read_bytes()
            sha = self._file_hash(content)
            now = time.time()
            v_id = f"v_{int(now)}_{sha[:8]}"

            # Criar pasta específica para o arquivo
            rel_name = path.name
            target_bak = self.storage_dir / f"{rel_name}_{v_id}.bak"
            target_bak.write_bytes(content)

            ver = SnapshotVersion(
                version_id=v_id,
                filepath=str(path.resolve()),
                timestamp=now,
                backup_path=str(target_bak.resolve()),
                file_size=len(content),
                hash_sha256=sha,
                change_summary=summary,
            )

            key = str(path.resolve())
            if key not in self._manifest:
                self._manifest[key] = []

            # Evita duplicar se a versão anterior tem o mesmo hash SHA256
            if self._manifest[key] and self._manifest[key][-1].get("hash_sha256") == sha:
                logger.debug("Snapshot idêntico já existe para %s. Ignorando duplicação.", key)
                return SnapshotVersion(**self._manifest[key][-1])

            self._manifest[key].append(ver.to_dict())
            self._save_manifest()

            logger.info("Snapshot '%s' criado para %s", v_id, path.name)
            return ver
        except Exception as exc:
            logger.error("Falha ao criar snapshot para %s: %s", filepath, exc)
            return None

    def list_snapshots(self, filepath: str) -> list[dict[str, Any]]:
        """Retorna histórico de snapshots gravados para um arquivo."""
        key = str(Path(filepath).resolve())
        return self._manifest.get(key, [])

    def rollback(self, filepath: str, version_id: str | None = None) -> tuple[bool, str]:
        """
        Restaura o arquivo para uma versão anterior.
        Se version_id for None, restaura para o último snapshot disponível.
        """
        key = str(Path(filepath).resolve())
        history = self._manifest.get(key, [])

        if not history:
            return False, f"Nenhum snapshot encontrado para o arquivo '{filepath}'."

        target_snap: dict[str, Any] | None = None
        if version_id:
            for snap in history:
                if snap.get("version_id") == version_id:
                    target_snap = snap
                    break
        else:
            # Pega o último snapshot válido
            target_snap = history[-1]

        if not target_snap:
            return False, f"Versão '{version_id}' não encontrada no histórico."

        bak_path = Path(target_snap["backup_path"])
        if not bak_path.exists():
            return False, f"Arquivo de backup físico '{bak_path}' não foi encontrado."

        try:
            # Restaura o conteúdo
            shutil.copy2(bak_path, filepath)
            logger.info("Rollback concluído com sucesso para %s (Versão: %s)", filepath, target_snap['version_id'])
            return True, f"Arquivo restaurado com sucesso para a versão {target_snap['version_id']} ({target_snap['readable_time']})."
        except Exception as exc:
            return False, f"Erro ao realizar rollback: {exc}"


# Instância global do gerenciador de snapshots
snapshot_manager = CodeSnapshotManager()
