"""
LLM Smart Auto-Router & Load Balancer — Roteador Inteligente e Failover Multi-Provedor
Roteia solicitações dinamicamente com base no tipo de tarefa e executa failover automático.

Categorias de Roteamento:
  - QUICK_CHAT: Respostas curtas / bate-papo ➔ Groq (Llama-3.3-70b / Qwen-2.5-72b)
  - CODE_REFLEXION: Programação, depuração, reflexion ➔ Claude Sonnet 4.6 / Gemini 3.6 Flash
  - VISION_MULTIMODAL: Análise visual, QR Code, prints ➔ Gemini 3.6 Flash / Qwen 3.6 Vision
  - REASONING_HEAVY: Raciocínio profundo, planos ➔ Claude Sonnet 4.6 / Gemini 3.6 Flash
"""
from __future__ import annotations

import re
import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


class TaskCategory(str, Enum):
    QUICK_CHAT = "quick_chat"
    CODE_REFLEXION = "code_reflexion"
    VISION_MULTIMODAL = "vision_multimodal"
    REASONING_HEAVY = "reasoning_heavy"


@dataclass
class RouteDecision:
    category: TaskCategory
    primary_provider: str
    primary_model: str
    fallback_provider: str
    fallback_model: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "primary_provider": self.primary_provider,
            "primary_model": self.primary_model,
            "fallback_provider": self.fallback_provider,
            "fallback_model": self.fallback_model,
            "reason": self.reason,
        }


class SmartLLMRouter:
    """Roteador dinâmico de modelos LLM com suporte a failover e balanceamento."""

    # Palavras-chave que indicam código ou raciocínio pesado
    CODE_KEYWORDS = {
        "def ", "function", "class ", "import ", "python", "javascript", "const ", "var ",
        "refatorar", "debug", "código", "erro", "traceback", "exception", "bug", "git",
        "script", "sql", "api", "html", "css", "docker", "test", "pytest"
    }

    REASONING_KEYWORDS = {
        "plano", "planejar", "arquitetura", "comparar", "analisar", "explicar detalhadamente",
        "como funciona", "passo a passo", "diferença entre", "estratégia"
    }

    def __init__(self, default_provider: str = "gemini") -> None:
        self.default_provider = default_provider.lower()
        self._provider_health: dict[str, bool] = {"gemini": True, "groq": True, "claude": True}
        self._last_error_time: dict[str, float] = {}

    def classify_prompt(self, prompt: str, has_image: bool = False) -> TaskCategory:
        """Classifica o tipo de tarefa com base no prompt e presença de imagem."""
        if has_image:
            return TaskCategory.VISION_MULTIMODAL

        text_lower = prompt.lower()
        words = set(re.findall(r"\w+", text_lower))

        if any(kw in text_lower for kw in self.CODE_KEYWORDS):
            return TaskCategory.CODE_REFLEXION

        if any(kw in text_lower for kw in self.REASONING_KEYWORDS) or len(prompt) > 400:
            return TaskCategory.REASONING_HEAVY

        if len(prompt) < 150 and not any(k in words for k in ("por que", "como", "explique")):
            return TaskCategory.QUICK_CHAT

        return TaskCategory.QUICK_CHAT

    def route(self, prompt: str, has_image: bool = False, requested_provider: str | None = None) -> RouteDecision:
        """Determina a melhor rota de modelo e os backups de failover."""
        category = self.classify_prompt(prompt, has_image=has_image)

        # Respeita o provedor explicitamente solicitado pelo usuário, se saudável
        if requested_provider and self.is_provider_healthy(requested_provider):
            prim_prov = requested_provider.lower()
            fall_prov = "groq" if prim_prov == "gemini" else "gemini"
            return RouteDecision(
                category=category,
                primary_provider=prim_prov,
                primary_model="gemini-2.5-flash" if prim_prov == "gemini" else "llama-3.3-70b-versatile",
                fallback_provider=fall_prov,
                fallback_model="llama-3.3-70b-versatile" if fall_prov == "groq" else "gemini-2.5-flash",
                reason=f"Provedor '{requested_provider}' solicitado pelo usuário.",
            )

        if category == TaskCategory.VISION_MULTIMODAL:
            return RouteDecision(
                category=category,
                primary_provider="gemini",
                primary_model="gemini-2.5-flash",
                fallback_provider="groq",
                fallback_model="qwen-2.5-coder-32b",
                reason="Tarefa com imagem/visão computacional.",
            )

        if category == TaskCategory.CODE_REFLEXION:
            return RouteDecision(
                category=category,
                primary_provider="gemini",
                primary_model="gemini-2.5-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Tarefa de programação/código detectada.",
            )

        if category == TaskCategory.REASONING_HEAVY:
            return RouteDecision(
                category=category,
                primary_provider="gemini",
                primary_model="gemini-2.5-flash",
                fallback_provider="groq",
                fallback_model="llama-3.3-70b-versatile",
                reason="Raciocínio complexo ou prompt longo.",
            )

        # QUICK_CHAT default
        return RouteDecision(
            category=category,
            primary_provider="groq" if self.is_provider_healthy("groq") else "gemini",
            primary_model="llama-3.3-70b-versatile" if self.is_provider_healthy("groq") else "gemini-2.5-flash",
            fallback_provider="gemini" if self.is_provider_healthy("groq") else "groq",
            fallback_model="gemini-2.5-flash",
            reason="Bate-papo rápido: priorizando resposta de alta velocidade.",
        )

    def mark_provider_error(self, provider: str) -> None:
        """Registra erro no provedor e ativa circuito de backup temporário por 60s."""
        prov = provider.lower()
        self._provider_health[prov] = False
        self._last_error_time[prov] = time.time()
        logger.warning("SmartLLMRouter: Marcando provedor '%s' com erro temporário.", prov)

    def is_provider_healthy(self, provider: str) -> bool:
        """Verifica se o provedor está saudável ou se o tempo de resfriamento (60s) expirou."""
        prov = provider.lower()
        if self._provider_health.get(prov, True):
            return True

        last_err = self._last_error_time.get(prov, 0)
        if time.time() - last_err > 60.0:  # 60 segundos de cooldown
            self._provider_health[prov] = True
            return True

        return False

    def execute_with_failover(
        self,
        prompt: str,
        func_gemini: Callable[[], Any],
        func_groq: Callable[[], Any],
        has_image: bool = False,
    ) -> tuple[Any, RouteDecision]:
        """
        Executa a função do provedor primário e alterna para o fallback se ocorrer exceção.
        """
        decision = self.route(prompt, has_image=has_image)

        primary_fn = func_gemini if decision.primary_provider == "gemini" else func_groq
        fallback_fn = func_groq if decision.primary_provider == "gemini" else func_gemini

        try:
            res = primary_fn()
            return res, decision
        except Exception as primary_exc:
            logger.warning("Falha no provedor primário (%s): %s. Tentando fallback...", decision.primary_provider, primary_exc)
            self.mark_provider_error(decision.primary_provider)
            try:
                res = fallback_fn()
                decision.reason += f" (Fallback executado devido a erro no {decision.primary_provider})"
                return res, decision
            except Exception as fallback_exc:
                raise RuntimeError(f"Ambos os provedores falharam. Primário ({decision.primary_provider}): {primary_exc}; Fallback ({decision.fallback_provider}): {fallback_exc}")
