"""
Recovery Engine — inspirado no private-agent
Gerenciador de resiliência e auto-recuperação para falhas de automação (mobile ou desktop).
Se uma ação de clique ou comando falhar, executa uma estratégia em 3 etapas de fallback.
"""
from __future__ import annotations

import time
from typing import Any, Callable


class RecoveryEngine:
    """Motor de auto-recuperação de automações."""

    @staticmethod
    def execute_with_recovery(
        primary_action: Callable[[], Any],
        fallback_action: Callable[[], Any] | None = None,
        reset_action: Callable[[], Any] | None = None,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """
        Executa uma ação com resiliência em 3 níveis:
        Nível 1: Tenta ação primária.
        Nível 2: Tenta fallback (ex: refazer dump da tela e re-clicar).
        Nível 3: Tenta reset (ex: voltar para Home / reiniciar aplicação) e re-executar.
        """
        # Tentativa 1 (Primária)
        try:
            res = primary_action()
            return {"ok": True, "level": 1, "result": res}
        except Exception as e1:
            pass

        # Tentativa 2 (Fallback)
        if fallback_action:
            try:
                time.sleep(0.5)
                res = fallback_action()
                return {"ok": True, "level": 2, "result": res, "recovered": True}
            except Exception as e2:
                pass

        # Tentativa 3 (Reset)
        if reset_action:
            try:
                time.sleep(1.0)
                reset_action()
                res = primary_action()
                return {"ok": True, "level": 3, "result": res, "recovered_via_reset": True}
            except Exception as e3:
                return {"ok": False, "error": f"Falha em todos os 3 níveis de auto-recuperação: {e3}"}

        return {"ok": False, "error": "Falha na execução primária sem fallback configurado."}
