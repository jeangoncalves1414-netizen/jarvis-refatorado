from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class Pattern:
    """Representa um padrão detectado."""
    action: str
    context: dict[str, Any]
    frequency: int = 0
    last_seen: float = 0
    confidence: float = 0.0


class PatternLearner:
    """Aprende padrões de comportamento do usuário para proatividade."""
    
    def __init__(self, min_occurrences: int = 3, time_window_hours: float = 24):
        self.min_occurrences = min_occurrences
        self.time_window_hours = time_window_hours
        self._patterns: dict[str, Pattern] = {}
        self._action_history: list[tuple[str, dict[str, Any], float]] = []
        self._max_history = 1000
        self._callbacks: list[Callable[[Pattern], None]] = []
    
    def record_action(self, action: str, context: dict[str, Any] | None = None):
        """Registra uma ação para análise de padrões."""
        context = context or {}
        timestamp = time.time()
        
        # Adiciona ao histórico
        self._action_history.append((action, context, timestamp))
        if len(self._action_history) > self._max_history:
            self._action_history.pop(0)
        
        # Atualiza ou cria padrão
        pattern_key = self._make_pattern_key(action, context)
        if pattern_key in self._patterns:
            pattern = self._patterns[pattern_key]
            pattern.frequency += 1
            pattern.last_seen = timestamp
            pattern.confidence = min(pattern.confidence + 0.1, 1.0)
        else:
            self._patterns[pattern_key] = Pattern(
                action=action,
                context=context,
                frequency=1,
                last_seen=timestamp,
                confidence=0.1
            )
        
        # Notifica callbacks se padrão está forte
        pattern = self._patterns[pattern_key]
        if pattern.frequency >= self.min_occurrences and pattern.confidence >= 0.5:
            for callback in self._callbacks:
                try:
                    callback(pattern)
                except Exception as e:
                    logger.error(f"Erro no callback de padrão: {e}")
    
    def _make_pattern_key(self, action: str, context: dict[str, Any]) -> str:
        """Cria chave única para padrão baseado em contexto relevante."""
        relevant_keys = {"time_of_day", "day_of_week", "app", "location"}
        relevant_context = {k: v for k, v in context.items() if k in relevant_keys}
        return f"{action}:{sorted(relevant_context.items())}"
    
    def get_suggestions(self, current_context: dict[str, Any] | None = None) -> list[Pattern]:
        """Retorna sugestões proativas baseadas em contexto atual."""
        current_context = current_context or {}
        current_time = time.time()
        
        suggestions = []
        time_window = self.time_window_hours * 3600
        
        for pattern in self._patterns.values():
            # Filtra padrões muito antigos
            if current_time - pattern.last_seen > time_window * 7:
                continue
            
            # Filtra por confiança mínima
            if pattern.confidence < 0.5:
                continue
            
            # Filtra por frequência mínima
            if pattern.frequency < self.min_occurrences:
                continue
            
            # Verifica se contexto é similar
            if self._context_matches(pattern.context, current_context):
                suggestions.append(pattern)
        
        # Ordena por confiança
        suggestions.sort(key=lambda p: p.confidence, reverse=True)
        return suggestions[:5]
    
    def _context_matches(self, pattern_context: dict[str, Any], current_context: dict[str, Any]) -> bool:
        """Verifica se contexto atual é similar ao padrão."""
        if not pattern_context:
            return True
        
        current_time = time.time()
        
        # Verifica hora do dia
        if "time_of_day" in pattern_context:
            pattern_hour = pattern_context["time_of_day"]
            current_hour = current_time % 86400 / 3600
            if abs(pattern_hour - current_hour) > 2:
                return False
        
        # Verifica dia da semana
        if "day_of_week" in pattern_context:
            pattern_day = pattern_context["day_of_week"]
            current_day = time.localtime(current_time).tm_wday
            if pattern_day != current_day:
                return False
        
        return True
    
    def add_callback(self, callback: Callable[[Pattern], None]):
        """Adiciona callback para quando padrão forte é detectado."""
        self._callbacks.append(callback)
    
    def get_context(self) -> dict[str, Any]:
        """Retorna contexto atual (hora, dia, etc)."""
        current_time = time.time()
        local_time = time.localtime(current_time)
        
        return {
            "time_of_day": current_time % 86400 / 3600,  # Hora em decimal
            "day_of_week": local_time.tm_wday,
            "hour": local_time.tm_hour,
            "minute": local_time.tm_min
        }
    
    def cleanup_old_patterns(self):
        """Remove padrões antigos e pouco frequentes."""
        current_time = time.time()
        time_window = self.time_window_hours * 3600 * 30  # 30 dias
        
        to_remove = []
        for key, pattern in self._patterns.items():
            if current_time - pattern.last_seen > time_window and pattern.frequency < 2:
                to_remove.append(key)
        
        for key in to_remove:
            del self._patterns[key]
        
        if to_remove:
            logger.info(f"Removidos {len(to_remove)} padrões antigos")
    
    def get_stats(self) -> dict[str, Any]:
        """Retorna estatísticas do aprendizado."""
        return {
            "total_patterns": len(self._patterns),
            "strong_patterns": sum(1 for p in self._patterns.values() if p.confidence >= 0.5),
            "total_actions": len(self._action_history),
            "avg_confidence": sum(p.confidence for p in self._patterns.values()) / len(self._patterns) if self._patterns else 0
        }
