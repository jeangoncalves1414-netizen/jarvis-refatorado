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
import contextvars
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
            specialist = self.coder
        elif task_type == "browser" or any(kw in task_lower for kw in ("site", "url", "http", "scraping", "navegar")):
            specialist = self.browser
        elif task_type == "research" or any(kw in task_lower for kw in ("pesquisar", "buscar", "artigo", "resumo", "relatório")):
            specialist = self.researcher
        else:
            specialist = self.coder
        return self._run_specialist(specialist, task_description, **kwargs)

    @staticmethod
    def _run_specialist(specialist: Any, task_description: str, **kwargs: Any) -> dict[str, Any]:
        """Executa o especialista e registra a etapa interna no pedido em andamento (C6)."""
        from app.agent.run_tracking import record_run_step

        name = str(getattr(specialist, "name", None) or type(specialist).__name__)
        record_run_step(f"Especialista {name} acionado.")
        try:
            result = specialist.execute_task(task_description, **kwargs)
        except Exception as exc:
            record_run_step(f"Especialista {name} falhou ({type(exc).__name__}).", kind="failure")
            raise
        if isinstance(result, dict) and result.get("ok") is True:
            record_run_step(f"Especialista {name} concluiu a tarefa.")
        else:
            reason = result.get("error") if isinstance(result, dict) else None
            reason = str(reason or "resultado inválido").rstrip(".")
            record_run_step(f"Especialista {name} não concluiu: {reason}.", kind="failure")
        return result

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
            # Cada tarefa leva uma cópia do contexto para as etapas caírem no pedido atual (C6).
            future_to_task = {executor.submit(contextvars.copy_context().run, _worker, task): task for task in tasks}
            for future in concurrent.futures.as_completed(future_to_task):
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    results.append({"ok": False, "error": str(exc)})

        return results


# Instância global do enxame
agent_swarm = AgentSwarmManager()
