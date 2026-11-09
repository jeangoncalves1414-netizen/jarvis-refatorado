"""Memory Vault Engine (inspirado no ai-memory-vault).

Gerencia um Vault de memória persistente em arquivos Markdown estruturados em data/vault/.
Oferece suporte a Daily Notes automáticas, Perfil de Usuário evolutivo, Notas de Priming
contextual por tipo de tarefa e busca rápida em texto.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

VAULT_DIR = Path("data/vault")
DAILY_NOTES_DIR = VAULT_DIR / "01-Daily-Notes"
PROFILE_DIR = VAULT_DIR / "02-User-Profile"
PRIMING_DIR = VAULT_DIR / "03-Priming-Notes"
PROJECTS_DIR = VAULT_DIR / "04-Projects"

PROFILE_FILE = PROFILE_DIR / "USER-PROFILE.md"


def ensure_vault_structure() -> None:
    """Garante que a estrutura de diretórios do Vault exista."""
    for folder in (DAILY_NOTES_DIR, PROFILE_DIR, PRIMING_DIR, PROJECTS_DIR):
        folder.mkdir(parents=True, exist_ok=True)
    
    if not PROFILE_FILE.exists():
        initial_profile = (
            "# 👤 Perfil do Usuário & Preferências\n\n"
            "## 📌 Informações Gerais\n"
            "- **Nome**: Usuário\n"
            "- **Estilo de Comunicação**: Direto, objetivo e técnico.\n\n"
            "## 💡 Preferências & Convenções\n"
            "- Prefere respostas sem enrolação ou disclaimers robóticos.\n"
            "- Prefere código limpo, comentado e testado.\n\n"
            "## 📑 Projetos Ativos\n"
            "- **Jarvis Desktop**: Assistente IA autônomo e multimodal.\n"
        )
        PROFILE_FILE.write_text(initial_profile, encoding="utf-8")

    # Iniciar notas de priming padrão se não existirem
    default_primings = {
        "coding.md": (
            "# 💻 Priming de Programação & Engenharia de Software\n\n"
            "- Escreva código modular, limpo e bem tipado.\n"
            "- Sempre trate exceções e evite usar try-except genéricos vazios.\n"
            "- Adicione docstrings explicativas e testes automatizados sempre que aplicável.\n"
        ),
        "writing.md": (
            "# ✍️ Priming de Redação & Conteúdo\n\n"
            "- Use um tom claro, envolvente e gramaticalmente impecável.\n"
            "- Evite clichês corporativos e adjetivos vazios.\n"
        ),
        "analysis.md": (
            "# 📊 Priming de Análise de Dados & Pesquisa\n\n"
            "- Apresente conclusões baseadas em evidências empíricas.\n"
            "- Destaque os principais achados em tópicos/tabelas scannable.\n"
        )
    }
    for filename, content in default_primings.items():
        filepath = PRIMING_DIR / filename
        if not filepath.exists():
            filepath.write_text(content, encoding="utf-8")


class MemoryVaultEngine:
    """Motor de gerenciamento do Vault de Memória em Markdown."""

    def __init__(self) -> None:
        ensure_vault_structure()

    def get_today_note_path(self) -> Path:
        today_str = datetime.now().strftime("%Y-%m-%d")
        return DAILY_NOTES_DIR / f"{today_str}.md"

    def get_or_create_daily_note(self) -> str:
        """Retorna o conteúdo da Daily Note de hoje, criando-a se necessário."""
        path = self.get_today_note_path()
        if not path.exists():
            today_str = datetime.now().strftime("%Y-%m-%d (%A)")
            header = (
                f"# 📅 Diário de Sessão - {today_str}\n\n"
                "## 📝 Log de Atividades & Aprendizados\n\n"
                "## 🎯 Continuidades & Tarefas Pendentes\n\n"
            )
            path.write_text(header, encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def append_daily_log(self, entry: str, category: str = "Atividade") -> bool:
        """Adiciona uma nova entrada rotulada ao diário de hoje."""
        if not entry or not entry.strip():
            return False
        path = self.get_today_note_path()
        self.get_or_create_daily_note()
        
        timestamp = datetime.now().strftime("%H:%M")
        formatted_entry = f"- **[{timestamp}] ({category})**: {entry.strip()}\n"
        
        content = path.read_text(encoding="utf-8")
        if "## 📝 Log de Atividades & Aprendizados" in content:
            parts = content.split("## 📝 Log de Atividades & Aprendizados")
            new_content = parts[0] + "## 📝 Log de Atividades & Aprendizados\n" + formatted_entry + parts[1]
        else:
            new_content = content + f"\n{formatted_entry}"
            
        path.write_text(new_content, encoding="utf-8")
        return True

    def get_user_profile(self) -> str:
        """Lê o arquivo de perfil do usuário."""
        if PROFILE_FILE.exists():
            return PROFILE_FILE.read_text(encoding="utf-8")
        return ""

    def update_user_profile_fact(self, fact: str) -> bool:
        """Adiciona um fato/preferência ao perfil do usuário."""
        if not fact or not fact.strip():
            return False
        content = self.get_user_profile()
        new_fact = f"- {fact.strip()}\n"
        if "## 💡 Preferências & Convenções" in content:
            parts = content.split("## 💡 Preferências & Convenções")
            updated = parts[0] + "## 💡 Preferências & Convenções\n" + new_fact + parts[1]
        else:
            updated = content + f"\n## 💡 Preferências & Convenções\n{new_fact}"
        PROFILE_FILE.write_text(updated, encoding="utf-8")
        return True

    def get_priming_context(self, task_type: str = "") -> str:
        """Retorna o texto de priming contextual para o tipo de tarefa."""
        task_type_lower = task_type.lower()
        if any(token in task_type_lower for token in ("code", "codigo", "program", "python", "bug", "dev")):
            file = PRIMING_DIR / "coding.md"
        elif any(token in task_type_lower for token in ("write", "texto", "redacao", "artigo", "email")):
            file = PRIMING_DIR / "writing.md"
        elif any(token in task_type_lower for token in ("analys", "analise", "dado", "pesquisa", "report")):
            file = PRIMING_DIR / "analysis.md"
        else:
            return ""
        
        if file.exists():
            return file.read_text(encoding="utf-8")
        return ""

    def save_note(self, title: str, content: str, folder: str = "04-Projects") -> str:
        """Salva uma nova nota Markdown no Vault."""
        clean_title = re.sub(r"[^\w\s-]", "", title).strip().replace(" ", "-")
        if not clean_title:
            clean_title = f"note-{int(time.time())}"
        
        target_dir = VAULT_DIR / folder
        try:
            target_dir.resolve().relative_to(Path(VAULT_DIR).resolve())
        except ValueError:
            raise ValueError("A pasta da nota precisa ficar dentro do cofre.") from None
        target_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = target_dir / f"{clean_title}.md"
        full_content = f"# {title}\n\n*Criado em: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n\n{content}\n"
        filepath.write_text(full_content, encoding="utf-8")
        return str(filepath)

    def search_vault(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Pesquisa termos em todos os arquivos Markdown no Vault."""
        query_terms = [t.lower() for t in re.findall(r"\w{3,}", query)]
        if not query_terms:
            return []
        
        results: list[dict[str, Any]] = []
        for filepath in VAULT_DIR.rglob("*.md"):
            try:
                text = filepath.read_text(encoding="utf-8")
                lines = text.splitlines()
                matches = 0
                snippet = ""
                for line in lines:
                    line_lower = line.lower()
                    if any(term in line_lower for term in query_terms):
                        matches += 1
                        if not snippet:
                            snippet = line.strip()
                if matches > 0:
                    results.append({
                        "file": filepath.name,
                        "path": str(filepath),
                        "matches": matches,
                        "snippet": snippet[:200],
                        "modified": os.path.getmtime(filepath)
                    })
            except Exception:
                continue
        
        results.sort(key=lambda r: (r["matches"], r["modified"]), reverse=True)
        return results[:limit]


# Instância global do motor
memory_vault = MemoryVaultEngine()
