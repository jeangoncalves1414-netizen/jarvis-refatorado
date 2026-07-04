from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.actions import FileActionService
from app.domain.productivity import ProductivityService


@dataclass(slots=True)
class AgentPlan:
    intent: str
    summary: str
    actions: list[str]
    context: dict[str, Any] = field(default_factory=dict)


class AgentOrchestrator:
    def __init__(
        self,
        settings: Any | None = None,
        llm_service: Any | None = None,
        memory_store: Any | None = None,
        file_action_service: Any | None = None,
        productivity_service: Any | None = None,
    ) -> None:
        self.settings = settings
        self.llm_service = llm_service
        self.memory_store = memory_store
        self.file_action_service = file_action_service or FileActionService()
        self.productivity_service = productivity_service or ProductivityService()
        self.last_plan: AgentPlan | None = None

    def _remember_preferences(self, text: str, normalized: str) -> None:
        if not self.memory_store:
            return

        if "prefiro" in normalized or "prefer" in normalized:
            if "curtas" in normalized or "curta" in normalized:
                self.memory_store.add_preference("preferred_response_style", "short")
            elif "detalh" in normalized:
                self.memory_store.add_preference("preferred_response_style", "detailed")

        if "me lembre" in normalized or "lembre" in normalized:
            self.memory_store.add_fact(text.strip())

    def handle_request(self, text: str) -> AgentPlan:
        normalized = (text or "").strip().lower()
        self._remember_preferences(text, normalized)
        plan: AgentPlan

        if any(token in normalized for token in ["arquivo", "pasta", "folder", "documento"]):
            action_result = None
            if self.file_action_service is not None:
                try:
                    action_result = self.file_action_service.execute(text)
                except Exception:
                    action_result = None
            plan = AgentPlan(
                intent="file",
                summary="O usuário quer gerenciar arquivos ou pastas.",
                actions=["listar arquivos", "ver contexto da pasta", "propor ação segura"],
                context={"action_result": action_result} if action_result else {},
            )
            self.last_plan = plan
            return plan

        if any(token in normalized for token in ["tarefa", "meta", "habito", "hábito", "progresso"]):
            task_title = ""
            if "tarefa" in normalized:
                parts = normalized.split("tarefa", 1)
                if len(parts) > 1:
                    task_title = parts[1].strip()
            if not task_title:
                task_title = normalized.replace("adicione", "").replace("crie", "").replace("uma", "").strip()
            task_title = task_title.replace("de", "", 1).strip()
            if task_title:
                self.productivity_service.add_task(task_title)
            plan = AgentPlan(
                intent="productivity",
                summary="O usuário quer organizar produtividade ou hábitos.",
                actions=["criar item", "registrar progresso", "sugerir próximo passo"],
                context={"task_title": task_title, "task_count": len(self.productivity_service.list_tasks())},
            )
            self.last_plan = plan
            return plan

        if any(token in normalized for token in ["voz", "áudio", "audio", "falar"]):
            return AgentPlan(
                intent="voice",
                summary="O usuário quer interação por voz.",
                actions=["ativar fluxo de voz", "capturar fala", "responder com síntese"],
            )

        plan = AgentPlan(
            intent="general",
            summary="O pedido é genérico e precisa de interpretação contextual.",
            actions=["compreender intenção", "escolher módulo", "responder de forma útil"],
            context={"memory_preferences": self.memory_store.get_preferences() if self.memory_store else []},
        )
        self.last_plan = plan
        return plan
