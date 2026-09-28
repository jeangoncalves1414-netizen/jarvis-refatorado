"""
AutoTune Sampling Engine — Fase 6
Ajusta dinamicamente os parâmetros de geração (temperature, top_p, frequency_penalty)
por categoria de request usando Exponential Moving Average (EMA) para aprendizado contínuo.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

AUTOTUNE_PATH = Path("data/autotune_state.json")

# Parâmetros padrão por categoria
DEFAULT_PARAMS: dict[str, dict[str, float]] = {
    "code": {"temperature": 0.2, "top_p": 0.85, "frequency_penalty": 0.1},
    "creative": {"temperature": 0.95, "top_p": 0.98, "frequency_penalty": 0.6},
    "analysis": {"temperature": 0.4, "top_p": 0.9, "frequency_penalty": 0.2},
    "factual": {"temperature": 0.1, "top_p": 0.8, "frequency_penalty": 0.0},
    "conversation": {"temperature": 0.7, "top_p": 0.95, "frequency_penalty": 0.3},
    "planning": {"temperature": 0.5, "top_p": 0.9, "frequency_penalty": 0.15},
    "default": {"temperature": 0.65, "top_p": 0.92, "frequency_penalty": 0.2},
}

EMA_ALPHA = 0.15  # Peso do EMA: quantos % a nova observação influencia (15%)

# Palavras-chave para classificação automática de intenção
INTENT_KEYWORDS: dict[str, list[str]] = {
    "code": ["código", "code", "função", "function", "debug", "script", "python", "javascript", "programar", "bug"],
    "creative": ["escreva", "crie", "historia", "poema", "criativ", "ficção", "imagine", "story"],
    "analysis": ["analis", "compara", "avali", "explica", "por que", "why", "porque", "pros e contras"],
    "factual": ["o que é", "what is", "quem é", "quando", "where", "quando foi", "definição"],
    "planning": ["plano", "plan", "roadmap", "etapas", "steps", "estratégia", "strategy"],
    "conversation": ["olá", "oi", "tudo bem", "como vai", "hey", "hi", "obrigado"],
}


def classify_intent(user_message: str) -> str:
    """Classifica a mensagem do usuário em uma categoria de intent."""
    msg_lower = user_message.lower()
    for category, keywords in INTENT_KEYWORDS.items():
        if any(kw in msg_lower for kw in keywords):
            return category
    return "default"


class AutoTuneSamplingEngine:
    """
    Motor de auto-tuning de parâmetros de geração.
    Aprende os melhores parâmetros para cada categoria de request via EMA.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state = self._load()

    def _load(self) -> dict[str, dict[str, float]]:
        if AUTOTUNE_PATH.exists():
            try:
                with open(AUTOTUNE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Merge with defaults to include any new categories
                merged = {k: v.copy() for k, v in DEFAULT_PARAMS.items()}
                merged.update(data)
                return merged
            except Exception:
                pass
        return {k: v.copy() for k, v in DEFAULT_PARAMS.items()}

    def _save(self) -> None:
        try:
            AUTOTUNE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(AUTOTUNE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def get_params(self, intent_category: str) -> dict[str, float]:
        """Retorna os parâmetros de sampling para uma categoria de intent."""
        with self._lock:
            return dict(self._state.get(intent_category, self._state["default"]))

    def get_params_for_message(self, user_message: str) -> tuple[str, dict[str, float]]:
        """Classifica a mensagem e retorna a categoria + parâmetros otimizados."""
        category = classify_intent(user_message)
        params = self.get_params(category)
        return category, params

    def record_feedback(
        self,
        intent_category: str,
        temperature: float | None = None,
        top_p: float | None = None,
        frequency_penalty: float | None = None,
        quality_signal: float = 1.0,
    ) -> None:
        """
        Registra feedback sobre os parâmetros usados para ajuste via EMA.
        quality_signal: 0.0 = péssimo, 1.0 = ótimo
        """
        with self._lock:
            if intent_category not in self._state:
                self._state[intent_category] = dict(DEFAULT_PARAMS.get(intent_category, DEFAULT_PARAMS["default"]))

            params = self._state[intent_category]
            effective_alpha = EMA_ALPHA * quality_signal  # Feedback negativo reduz a influência

            if temperature is not None:
                params["temperature"] = (1 - effective_alpha) * params["temperature"] + effective_alpha * temperature
            if top_p is not None:
                params["top_p"] = (1 - effective_alpha) * params["top_p"] + effective_alpha * top_p
            if frequency_penalty is not None:
                params["frequency_penalty"] = (1 - effective_alpha) * params["frequency_penalty"] + effective_alpha * frequency_penalty

            self._save()

    def reset_category(self, intent_category: str) -> None:
        """Reseta os parâmetros de uma categoria para os defaults."""
        with self._lock:
            if intent_category in DEFAULT_PARAMS:
                self._state[intent_category] = DEFAULT_PARAMS[intent_category].copy()
            elif intent_category in self._state:
                del self._state[intent_category]
            self._save()

    def get_all_params(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {k: dict(v) for k, v in self._state.items()}
