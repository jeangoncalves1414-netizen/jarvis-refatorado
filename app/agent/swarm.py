"""
Swarm Manager: Gerenciador, Roteador e Paralelizador do Enxame de Sub-Agentes.
Suporta:
  - Rotação dinâmica de múltiplas API Keys do .env (GEMINI_API_KEYS / GROQ_API_KEYS)
  - Execução assíncrona/paralela de sub-agentes com isolamento de chave
  - Fusão e síntese de resultados em tempo recorde
"""
from __future__ import annotations

import os
import itertools
import concurrent.futures
from typing import Any
from app.agent.subagents.coder_subagent import CoderSubagent
from app.agent.subagents.browser_subagent import BrowserSubagent
from app.agent.subagents.research_subagent import ResearchSubagent


class APIKeyRotator:
    """Gerencia e rotaciona múltiplas API keys a partir de variáveis de ambiente."""

    def __init__(self, env_var_prefix: str = "GEMINI_API_KEY") -> None:
        self.keys: list[str] = []
        self._load_keys(env_var_prefix)
        self._cycler = itertools.cycle(self.keys) if self.keys else None

    def _load_keys(self, prefix: str) -> None:
        # 1. Checa por lista separada por vírgulas: GEMINI_API_KEYS="key1,key2,key3"
        csv_keys = os.getenv(f"{prefix}S", "") or os.getenv(f"{prefix}_LIST", "")
        if csv_keys:
            self.keys.extend([k.strip() for k in csv_keys.split(",") if k.strip()])

        # 2. Checa por padrão numerado: GEMINI_API_KEY_1, GEMINI_API_KEY_2, ...
        for i in range(1, 10):
            k = os.getenv(f"{prefix}_{i}", "").strip()
            if k and k not in self.keys:
                self.keys.append(k)

        # 3. Fallback para a chave padrão única
        single_key = os.getenv(prefix, "").strip()
        if single_key and single_key not in self.keys:
            self.keys.append(single_key)

    def get_next_key( me ) -> str:
        if not me.keys:
            return ""
        return next(me._cycler) if me._cycler else me.keys[0]


class AgentSwarmManager:
    """Orquestra a execução individual ou em enxame paralelo de sub-agentes com rotação de chaves."""

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service
        self.coder = CoderSubagent(llm_service=llm_service)
        self.browser = BrowserSubagent(llm_service=llm_service)
        self.researcher = ResearchSubagent(llm_service=llm_service)
        self.key_rotator = APIKeyRotator("GEMINI_API_KEY")

    def route_and_execute(self, task_description: str, task_type: str = "auto", **kwargs: Any) -> dict[str, Any]:
        """Roteia a tarefa para o sub-agente especialista correto."""
        task_lower = task_description.lower()

        # Atribui chave rotacionada se disponível
        api_key = self.key_rotator.get_next_key()
        if api_key:
            kwargs["api_key"] = api_key

        if task_type == "coder" or any(kw in task_lower for kw in ("code", "python", "bug", "função", "script", "refatorar")):
            return self.coder.execute_task(task_description, **kwargs)
        elif task_type == "browser" or any(kw in task_lower for kw in ("site", "url", "http", "scraping", "navegar")):
            return self.browser.execute_task(task_description, **kwargs)
        elif task_type == "research" or any(kw in task_lower for kw in ("pesquisar", "buscar", "artigo", "resumo", "relatório")):
            return self.researcher.execute_task(task_description, **kwargs)
        else:
            return self.coder.execute_task(task_description, **kwargs)

    def execute_swarm_parallel(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Executa múltiplas sub-tarefas de enxame em paralelo com rotação de API Keys."""
        results: list[dict[str, Any]] = []
        if not tasks:
            return results

        def _worker(t: dict[str, Any]) -> dict[str, Any]:
            desc = t.get("description", "")
            t_type = t.get("type", "auto")
            return self.route_and_execute(desc, task_type=t_type, **t)

        with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(tasks), 5)) as executor:
            future_to_task = {executor.submit(_worker, task): task for task in tasks}
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    results.append({"ok": False, "error": str(exc)})

        return results


# Instância global do enxame
agent_swarm = AgentSwarmManager()
