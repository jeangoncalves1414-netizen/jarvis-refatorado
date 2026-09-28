"""Testes unitários automatizados para o Multi-LLM Racing Engine (G0DM0D3/ULTRAPLINIAN)."""
from __future__ import annotations

import unittest
from app.services.llm_racing import MultiLLMRacingService, llm_racing_service


class TestLLMRacingService(unittest.TestCase):

    def test_mock_llm_racing_execution(self):
        def mock_groq(p: str) -> str:
            return "Resposta rápida do Groq"

        def mock_gemini(p: str) -> str:
            import time
            time.sleep(0.1)
            return "Resposta do Gemini"

        candidates = [("Groq", mock_groq), ("Gemini", mock_gemini)]
        res = llm_racing_service.race_prompt("Qual a capital da França?", candidates=candidates, timeout=5.0)

        self.assertTrue(res["ok"])
        self.assertEqual(res["winner_provider"], "Groq")
        self.assertIn("Resposta rápida do Groq", res["response"])
        self.assertIn("⚡", res["badge"])
        self.assertGreater(res["elapsed_ms"], 0)

    def test_empty_candidates_fallback(self):
        res = MultiLLMRacingService().race_prompt("Teste com candidatos vazios", candidates=[], timeout=1.0)
        self.assertFalse(res["ok"])
        self.assertIn("Nenhum provedor", res["error"])


if __name__ == "__main__":
    unittest.main()
