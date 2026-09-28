"""Testes unitários e de integração para os 5 novos módulos de referência desktop do Jarvis."""
from __future__ import annotations

import unittest
from app.services.memory_vault import memory_vault
from app.services.stm_filters import stm_filter
from app.services.tool_forge import tool_forge
from app.agent.tools.desktop_search import DesktopSearchTool
from app.agent.tools.smart_drop_zone import SmartDropZoneTool
from app.agent.tools.phantom_typer import PhantomTyperTool


class TestDesktopModules(unittest.TestCase):

    def test_memory_vault_engine(self):
        # 1. Daily note log
        ok = memory_vault.append_daily_log("Testando integração do Memory Vault", category="Teste")
        self.assertTrue(ok)
        
        content = memory_vault.get_or_create_daily_note()
        self.assertIn("Testando integração do Memory Vault", content)

        # 2. User Profile update
        ok_prof = memory_vault.update_user_profile_fact("Prefere testes automatizados com unittest")
        self.assertTrue(ok_prof)
        self.assertIn("unittest", memory_vault.get_user_profile())

        # 3. Priming note retrieval
        priming = memory_vault.get_priming_context("coding python")
        self.assertIn("Programação", priming)

        # 4. Search vault
        search_res = memory_vault.search_vault("unittest")
        self.assertGreaterEqual(len(search_res), 1)

    def test_stm_filters(self):
        input_text = "Com certeza! Aqui está o código que você pediu:\n\ndef hello():\n    pass"
        clean = stm_filter.process(input_text)
        self.assertFalse(clean.startswith("Com certeza"))
        self.assertIn("def hello():", clean)

        hesitation_input = "Eu acho que a resposta correta é 42."
        clean_hesitation = stm_filter.filter_hesitations(hesitation_input)
        self.assertNotIn("acho que", clean_hesitation.lower())

    def test_tool_forge_engine(self):
        sample_code = """
from app.agent.tools.base import BaseTool

class DummyCustomTool(BaseTool):
    name = "dummy_custom"
    description = "Dummy tool test"
    def run(self, **kwargs):
        return {"success": True}
"""
        valid, msg = tool_forge.validate_code_ast(sample_code)
        self.assertTrue(valid)

        invalid_code = "def syntax error ("
        valid_inv, msg_inv = tool_forge.validate_code_ast(invalid_code)
        self.assertFalse(valid_inv)

    def test_desktop_search_tool(self):
        tool = DesktopSearchTool()
        res = tool.run(query="README", max_results=5)
        self.assertTrue(res["success"])
        self.assertGreaterEqual(res["count"], 0)

    def test_smart_drop_zone_tool(self):
        tool = SmartDropZoneTool()
        res = tool.run(target_folder="Downloads")
        self.assertTrue(res["success"])

    def test_phantom_typer_tool(self):
        tool = PhantomTyperTool()
        # Test dry-run with empty text validation
        res = tool.run(text="")
        self.assertFalse(res["success"])


if __name__ == "__main__":
    unittest.main()
