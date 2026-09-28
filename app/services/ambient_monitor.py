"""Ambient Proactive Monitor: Monitoramento Silencioso de Erros de Tela/Terminal e Sugestões 1-Click Fix."""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AmbientAlert:
    id: str
    timestamp: float
    title: str
    source: str
    error_snippet: str
    suggested_fix: str
    severity: str = "warning"  # "info" | "warning" | "error"


class AmbientMonitorEngine:
    """Motor de monitoramento ambiente em segundo plano."""

    def __init__(self, llm_service: Any = None) -> None:
        self.llm_service = llm_service
        self.active_alerts: list[AmbientAlert] = []
        self._last_clipboard_check: str = ""

    def inspect_clipboard_for_errors(self) -> AmbientAlert | None:
        """Verifica se o conteúdo atual da área de transferência contém um traceback de erro."""
        try:
            import pyperclip
            text = pyperclip.paste()
        except Exception:
            return None

        if not text or text == self._last_clipboard_check or len(text) < 15:
            return None

        self._last_clipboard_check = text

        # Padrões comuns de exceções em Python/Node/Windows
        error_patterns = [
            r"Traceback \(most recent call last\):",
            r"SyntaxError: .+",
            r"AttributeError: .+",
            r"KeyError: .+",
            r"ImportError: .+",
            r"TypeError: .+",
            r"Uncaught TypeError: .+",
        ]

        matched = False
        for pattern in error_patterns:
            if re.search(pattern, text):
                matched = True
                break

        if not matched:
            return None

        alert_id = f"alert_{int(time.time())}"
        snippet = text[:300]
        suggested_fix = self._generate_fix_suggestion(snippet)

        alert = AmbientAlert(
            id=alert_id,
            timestamp=time.time(),
            title="Erro Detectado na Área de Transferência",
            source="Clipboard Monitor",
            error_snippet=snippet,
            suggested_fix=suggested_fix,
            severity="error"
        )
        self.active_alerts.append(alert)
        # Mantém apenas os últimos 10 alertas
        if len(self.active_alerts) > 10:
            self.active_alerts.pop(0)

        return alert

    def _generate_fix_suggestion(self, error_snippet: str) -> str:
        if not self.llm_service:
            return "Sugestão: Verifique os tipos de variáveis e imports do módulo."

        prompt = (
            f"Analise este erro capturado no terminal do usuário:\n```\n{error_snippet}\n```\n\n"
            "Forneça uma explicação direta e uma sugestão de correção em 2 frases."
        )
        try:
            return self.llm_service.ask(prompt)
        except Exception:
            return "Verifique a declaração e os módulos importados."

    def get_alerts(self) -> list[dict[str, Any]]:
        """Retorna todos os alertas ativos em formato dict."""
        return [
            {
                "id": a.id,
                "timestamp": a.timestamp,
                "title": a.title,
                "source": a.source,
                "error_snippet": a.error_snippet,
                "suggested_fix": a.suggested_fix,
                "severity": a.severity
            }
            for a in self.active_alerts
        ]


# Instância global do monitor ambiente
ambient_monitor = AmbientMonitorEngine()
