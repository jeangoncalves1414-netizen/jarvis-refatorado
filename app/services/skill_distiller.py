"""Skill Distiller Engine: Auto-Destilação de Habilidades e Aprendizado de Ferramentas.

Analisa trajetórias bem-sucedidas do ReAct e sequências de tarefas do Orquestrador,
sintetizando autonomamente novas ferramentas Python registradas no Vault de Tools.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Any
from app.services.tool_forge import tool_forge
from app.agent.tools.registry import registry

CUSTOM_TOOLS_DIR = Path("app/agent/tools/custom")


class SkillDistillerEngine:
    """Motor de destilação autônoma de trajetórias em novas ferramentas."""

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service

    def distill_trajectory_to_skill(
        self,
        skill_name: str,
        description: str,
        trajectory_steps: list[dict[str, Any]]
    ) -> tuple[bool, str]:
        """Sintetiza uma nova ferramenta Python no Tool Forge a partir dos passos de uma trajetória."""
        if not skill_name or not trajectory_steps:
            return False, "Nome da habilidade ou passos da trajetória não informados."

        clean_name = re.sub(r"[^\w_]", "", skill_name.lower().strip().replace("-", "_"))
        if not clean_name:
            clean_name = f"auto_skill_{int(time.time())}"

        steps_summary = []
        for i, step in enumerate(trajectory_steps, 1):
            action = step.get("tool_name", step.get("action_type", "step"))
            args = step.get("tool_args", {})
            obs = step.get("observation", "")
            steps_summary.append(f"Passo {i}: {action}({args}) -> Result: {obs[:100]}")

        prompt = (
            f"Crie o código de uma ferramenta Python personalizada chamada '{clean_name}'.\n"
            f"Descrição da Ferramenta: {description}\n"
            f"Sequência de Passos que ela deve automatizar:\n" + "\n".join(steps_summary) + "\n\n"
            "Retorne o código Python interno que executa essa lógica no método run(**kwargs). "
            "Retorne dict com {'success': True, 'result': ...}. Não inclua marcações markdown no código."
        )

        if self.llm_service:
            raw_code = self.llm_service.ask(prompt)
        else:
            raw_code = f"return {{'success': True, 'result': 'Habilidade autônoma {clean_name} executada.'}}"

        clean_code = raw_code.replace("```python", "").replace("```", "").strip()

        # Gera o template BaseTool via Tool Forge
        full_tool_code = tool_forge.generate_tool_template(clean_name, description, clean_code)

        # Salva e registra a ferramenta
        success, msg = tool_forge.save_and_register_tool(clean_name, full_tool_code)
        if success:
            # Registra no registro de ferramentas em memória do agente
            try:
                registry.register_custom_tools()
            except Exception:
                pass
            return True, f"Habilidade '{clean_name}' destilada e salva em custom/{clean_name}.py"
        return False, f"Falha ao destilar habilidade: {msg}"


# Instância global do destilador
skill_distiller = SkillDistillerEngine()
