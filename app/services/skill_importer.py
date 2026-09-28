"""Importador e Gerenciador de Habilidades de Segurança.

Importa playbooks e especificações de habilidades do repositório reverse-skill para o workspace Jarvis.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

WORKSPACE_SKILLS_DIR = Path(".agents/skills")
SOURCE_SKILLS_DIR = Path("data/temp_repos/reverse_skill/reverse-skill-main/skills")


class SkillImporterEngine:
    """Motor de importação e catalogação de habilidades de segurança."""

    def __init__(self) -> None:
        WORKSPACE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    def import_skill(self, skill_name: str) -> dict[str, Any]:
        """Importa uma habilidade específica do repositório clonado."""
        if not skill_name:
            return {"ok": False, "error": "Nome da habilidade não informado."}

        src_path = SOURCE_SKILLS_DIR / skill_name
        if not src_path.exists():
            return {"ok": False, "error": f"Habilidade '{skill_name}' não encontrada no repositório de origem."}

        dest_path = WORKSPACE_SKILLS_DIR / skill_name
        try:
            if dest_path.exists():
                shutil.rmtree(dest_path)
            shutil.copytree(src_path, dest_path)
            return {
                "ok": True,
                "skill": skill_name,
                "installed_path": str(dest_path),
                "message": f"Habilidade '{skill_name}' importada com sucesso para .agents/skills/{skill_name}"
            }
        except Exception as exc:
            return {"ok": False, "error": f"Falha ao copiar habilidade: {exc}"}

    def list_available_source_skills(self) -> list[str]:
        """Lista todas as habilidades disponíveis no repositório de origem."""
        if not SOURCE_SKILLS_DIR.exists():
            return []
        skills = []
        for item in SOURCE_SKILLS_DIR.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.append(item.name)
        return sorted(skills)


# Instância global do importador
skill_importer = SkillImporterEngine()
