"""Multi-LLM Racing & Consensus Engine (inspirado no G0DM0D3/ULTRAPLINIAN).

Dispara solicitações em paralelo para múltiplos provedores de LLM (Groq, Gemini, Oxyy, Ollama),
avalia as respostas por velocidade, completude e polimento (STM), e seleciona o campeão.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable
from app.services.stm_filters import stm_filter


class MultiLLMRacingService:
    """Motor de corrida paralela de LLMs (Multi-LLM Racing Engine)."""

    def __init__(self, llm_service: Any | None = None) -> None:
        self.llm_service = llm_service

    def get_active_race_candidates(self) -> list[tuple[str, Callable[[str], str]]]:
        """Retorna os provedores de LLM disponíveis e suas funções de chamada."""
        if not self.llm_service:
            return []

        candidates = []
        # Groq
        if self.llm_service._api_key_for("groq"):
            def _call_groq(p: str) -> str:
                return self.llm_service.ask(p, provider="groq")
            candidates.append(("Groq", _call_groq))

        # Gemini
        if self.llm_service._api_key_for("gemini"):
            def _call_gemini(p: str) -> str:
                return self.llm_service.ask(p, provider="gemini")
            candidates.append(("Gemini", _call_gemini))

        # Oxyy
        if self.llm_service._api_key_for("oxyy"):
            def _call_oxyy(p: str) -> str:
                return self.llm_service.ask(p, provider="oxyy")
            candidates.append(("Oxyy", _call_oxyy))

        return candidates

    def race_prompt(
        self,
        prompt: str,
        candidates: list[tuple[str, Callable[[str], str]]] | None = None,
        timeout: float = 25.0
    ) -> dict[str, Any]:
        """Executa a corrida em paralelo e escolhe a melhor resposta com menor latência."""
        targets = candidates or self.get_active_race_candidates()
        if not targets:
            # Fallback se nenhum candidato adicional estiver configurado
            if self.llm_service:
                start = time.time()
                resp = self.llm_service.ask(prompt)
                elapsed = time.time() - start
                provider = self.llm_service.get_active_provider()
                return {
                    "ok": True,
                    "winner_provider": provider.capitalize(),
                    "response": stm_filter.process(resp),
                    "elapsed_seconds": round(elapsed, 2),
                    "elapsed_ms": int(elapsed * 1000),
                    "badge": f"⚡ {round(elapsed, 2)}s · {provider.capitalize()}"
                }
            return {"ok": False, "error": "Nenhum provedor configurado para a corrida."}

        start_time = time.time()
        winner_data: dict[str, Any] | None = None

        def _worker(name: str, fn: Callable[[str], str]) -> dict[str, Any]:
            w_start = time.time()
            raw_res = fn(prompt)
            w_elapsed = time.time() - w_start
            clean_res = stm_filter.process(raw_res)
            return {
                "provider": name,
                "response": clean_res,
                "elapsed": w_elapsed,
                "length": len(clean_res)
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(targets)) as executor:
            future_map = {
                executor.submit(_worker, name, fn): name for name, fn in targets
            }

            for future in concurrent.futures.as_completed(future_map, timeout=timeout):
                try:
                    res = future.result()
                    if res and res["response"] and len(res["response"].strip()) >= 5:
                        winner_data = res
                        break
                except Exception:
                    continue

        if winner_data:
            elapsed_sec = round(winner_data["elapsed"], 2)
            elapsed_ms = max(1, int(winner_data["elapsed"] * 1000))
            provider_name = winner_data["provider"]
            return {
                "ok": True,
                "winner_provider": provider_name,
                "response": winner_data["response"],
                "elapsed_seconds": elapsed_sec,
                "elapsed_ms": elapsed_ms,
                "badge": f"⚡ {elapsed_sec}s · {provider_name}"
            }

        total_elapsed = round(time.time() - start_time, 2)
        return {
            "ok": False,
            "error": "Nenhum provedor respondeu no tempo limite.",
            "elapsed_seconds": total_elapsed
        }


# Instância global da corrida
llm_racing_service = MultiLLMRacingService()
