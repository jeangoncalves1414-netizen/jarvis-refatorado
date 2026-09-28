"""Testes unitários automatizados para o Hacker Terminal & Motor de Permissões estilo Hacker.ai."""
from __future__ import annotations

import unittest
from app.services.hacker_terminal import HackerTerminalEngine
from app.agent.tools.hacker_mode import HackerModeTool


class TestHackerTerminal(unittest.TestCase):

    def test_policy_modes_switching(self):
        engine = HackerTerminalEngine(llm_service=None, initial_policy="ask_every_time")
        self.assertEqual(engine.policy_mode, "ask_every_time")

        self.assertTrue(engine.set_policy_mode("allow_specific"))
        self.assertEqual(engine.policy_mode, "allow_specific")

        self.assertTrue(engine.set_policy_mode("direct_execution"))
        self.assertEqual(engine.policy_mode, "direct_execution")

        self.assertFalse(engine.set_policy_mode("invalid_mode"))

    def test_command_analysis_and_risk(self):
        engine = HackerTerminalEngine(llm_service=None)
        res_low = engine.analyze_command("git status")
        self.assertTrue(res_low["ok"])
        self.assertEqual(res_low["risk_level"], "low")
        self.assertTrue(res_low["is_whitelisted"])

        res_high = engine.analyze_command("rm -rf /")
        self.assertEqual(res_high["risk_level"], "high")

    def test_ask_every_time_policy(self):
        engine = HackerTerminalEngine(llm_service=None, initial_policy="ask_every_time")
        res = engine.prepare_or_execute("echo 'Hello World'")
        self.assertEqual(res["status"], "pending_approval")
        self.assertIn("cmd_", res["cmd_id"])

        # Aprovação manual
        cmd_id = res["cmd_id"]
        exec_res = engine.approve_and_execute(cmd_id)
        self.assertEqual(exec_res["status"], "executed")
        self.assertTrue(exec_res["ok"])
        self.assertIn("Hello World", exec_res["output"])

    def test_allow_specific_policy(self):
        engine = HackerTerminalEngine(llm_service=None, initial_policy="allow_specific")
        
        # Comando na lista branca executa direto
        res_white = engine.prepare_or_execute("git status")
        self.assertEqual(res_white["status"], "executed")

        # Comando fora da lista branca pede confirmação
        res_other = engine.prepare_or_execute("python -c \"print('custom')\"")
        self.assertEqual(res_other["status"], "pending_approval")

    def test_direct_execution_policy(self):
        engine = HackerTerminalEngine(llm_service=None, initial_policy="direct_execution")
        res = engine.prepare_or_execute("echo 'Direct Run'")
        self.assertEqual(res["status"], "executed")
        self.assertIn("Direct Run", res["output"])

    def test_hacker_mode_tool(self):
        tool = HackerModeTool()
        res = tool.run(command="echo 'Tool Test'", force=True)
        self.assertEqual(res["status"], "executed")
        self.assertTrue(res["ok"])


if __name__ == "__main__":
    unittest.main()
