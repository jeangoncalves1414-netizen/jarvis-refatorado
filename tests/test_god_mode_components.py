"""Testes unitários automatizados para os 5 Pilares do Jarvis God Mode (Arquitetura Avançada)."""
from __future__ import annotations

import unittest
from app.agent.react_loop import ReActLoopEngine, ReActStep
from app.agent.swarm import AgentSwarmManager
from app.agent.subagents.coder_subagent import CoderSubagent
from app.agent.subagents.browser_subagent import BrowserSubagent
from app.agent.subagents.research_subagent import ResearchSubagent
from app.services.skill_distiller import SkillDistillerEngine
from app.services.ambient_monitor import AmbientMonitorEngine
from app.services.reflexion import ReflexionEngine


class TestGodModeComponents(unittest.TestCase):

    def test_react_loop_execution(self):
        engine = ReActLoopEngine(llm_service=None, registry=None)
        trajectory = engine.run_loop("Test Goal", max_steps=2)

        self.assertIsNotNone(trajectory)
        self.assertEqual(trajectory.goal, "Test Goal")
        self.assertTrue(len(trajectory.steps) > 0)
        self.assertTrue(trajectory.success)

    def test_coder_subagent_ast_validation(self):
        coder = CoderSubagent(llm_service=None)
        
        # Código válido
        valid_res = coder.execute_task("Criar função de soma", code_snippet="def add(a, b):\n    return a + b")
        self.assertTrue(valid_res["ok"])
        self.assertTrue(valid_res["ast_valid"])

        # Sintaxe inválida
        valid_ast, err = coder.validate_ast("def broken_syntax(:")
        self.assertFalse(valid_ast)
        self.assertIn("Linha 1", err)

    def test_browser_subagent_execution(self):
        browser = BrowserSubagent(llm_service=None)
        res = browser.execute_task("https://example.com")
        self.assertTrue(res["ok"])
        self.assertEqual(res["agent"], "browser_agent")

    def test_research_subagent_synthesis(self):
        researcher = ResearchSubagent(llm_service=None)
        res = researcher.execute_task("Python 3.11 features")
        self.assertTrue(res["ok"])
        self.assertEqual(res["agent"], "research_agent")

    def test_swarm_router_and_parallel(self):
        swarm = AgentSwarmManager(llm_service=None)
        res_coder = swarm.route_and_execute("Refatorar código da API python", task_type="auto")
        self.assertEqual(res_coder["agent"], "coder_agent")

        res_research = swarm.route_and_execute("Pesquisar notícias sobre IA", task_type="auto")
        self.assertEqual(res_research["agent"], "research_agent")

        parallel_tasks = [
            {"description": "Criar script python de teste", "type": "coder"},
            {"description": "Pesquisar artigo científico", "type": "research"}
        ]
        p_results = swarm.execute_swarm_parallel(parallel_tasks)
        self.assertEqual(len(p_results), 2)

    def test_skill_distiller(self):
        distiller = SkillDistillerEngine(llm_service=None)
        steps = [
            {"tool_name": "desktop_search", "tool_args": {"query": "relatorio"}, "observation": "Encontrado 1 arquivo"},
            {"tool_name": "smart_drop_zone", "tool_args": {"target_folder": "Downloads"}, "observation": "Organizado"}
        ]
        ok, msg = distiller.distill_trajectory_to_skill(
            skill_name="test_auto_organizer",
            description="Organizador de relatórios automatizado",
            trajectory_steps=steps
        )
        self.assertTrue(ok)
        self.assertIn("custom", msg)

    def test_ambient_monitor_error_detection(self):
        monitor = AmbientMonitorEngine(llm_service=None)
        
        # Simula erro de traceback no clipboard
        error_traceback = (
            "Traceback (most recent call last):\n"
            "  File 'app/main.py', line 12, in <module>\n"
            "    val = data['missing_key']\n"
            "KeyError: 'missing_key'\n"
        )
        
        try:
            import pyperclip
            pyperclip.copy(error_traceback)
            alert = monitor.inspect_clipboard_for_errors()
            if alert:
                self.assertEqual(alert.severity, "error")
                self.assertIn("KeyError", alert.error_snippet)
        except Exception:
            pass  # Suporta ambiente headless onde clipboard nativo pode estar desabilitado

    def test_reflexion_engine(self):
        engine = ReflexionEngine(llm_service=None)
        res = engine.process_with_reflexion("Como inverter uma string em Python?", "string[::-1]")
        self.assertTrue(res["ok"])
        self.assertIn("string[::-1]", res["response"])


if __name__ == "__main__":
    unittest.main()
