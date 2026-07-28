from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass
class GuardrailDecision:
    allow: bool
    reason: str = ""


class ToolGuardrails:
    """Proteção contra loops e repetições."""
    
    def __init__(self, repeat_limit: int = 3, no_progress_limit: int = 3):
        self.repeat_limit = repeat_limit
        self.no_progress_limit = no_progress_limit
        self._calls: dict[str, int] = {}
        self._results: dict[tuple[str, str], int] = {}
    
    def before_call(self, tool: str, args: Mapping[str, Any]) -> GuardrailDecision:
        """Verifica antes de executar ferramenta."""
        key = self._key(tool, args)
        if self._calls.get(key, 0) >= self.repeat_limit:
            return GuardrailDecision(False, f"Repetição bloqueada: {tool}")
        self._calls[key] = self._calls.get(key, 0) + 1
        return GuardrailDecision(True)
    
    def after_call(self, tool: str, args: Mapping[str, Any], result: Any) -> GuardrailDecision:
        """Verifica após executar ferramenta."""
        text = self._normalize(result)
        key = (tool, text)
        self._results[key] = self._results.get(key, 0) + 1
        
        if self._results[key] >= self.no_progress_limit and self._is_no_progress(text):
            return GuardrailDecision(False, f"Sem progresso: {tool}")
        return GuardrailDecision(True)
    
    def reset(self) -> None:
        """Reseta contadores."""
        self._calls.clear()
        self._results.clear()
    
    def _key(self, tool: str, args: Mapping[str, Any]) -> str:
        try:
            return f"{tool}:{json.dumps(args or {}, sort_keys=True)}"
        except TypeError:
            return f"{tool}:{repr(args)}"
    
    def _normalize(self, result: Any) -> str:
        return " ".join(str(result or "").lower().split())[:200]
    
    def _is_no_progress(self, text: str) -> bool:
        markers = {"sem resultado", "falhou", "erro", "não executado"}
        return any(m in text for m in markers)
