"""
Smoke Test suite for Jarvis core services & APIs.
Run with: python tests/smoke_test.py
"""

import unittest
import os
import sys
import json
import tempfile
from unittest import mock

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app.agent.tools.clipboard as clipboard_module
import app.core.logger as logger_module
import app.storage.session_store as session_store_module
from app.core.logger import logger
from app.storage.user_preferences import preference_store
from app.agent.tools.clipboard import add_clipboard_history, get_clipboard_history
from app.storage.session_store import save_session_history, get_session_history

class TestJarvisSmoke(unittest.TestCase):

    def setUp(self):
        """Preferências, sessões, clipboard, logs e índices vão para um diretório temporário, nunca para data/."""
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.tmp_dir = tmp.name
        for target, attribute, value in (
            (preference_store, "file_path", os.path.join(self.tmp_dir, "preferences.json")),
            (session_store_module, "SESSIONS_FILE", os.path.join(self.tmp_dir, "sessions.json")),
            (clipboard_module, "DATA_DIR", self.tmp_dir),
            (clipboard_module, "CLIPBOARD_FILE", os.path.join(self.tmp_dir, "clipboard_history.json")),
            (logger_module, "LOGS_FILE", os.path.join(self.tmp_dir, "logs.jsonl")),
        ):
            patcher = mock.patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_01_logger_structured(self):
        """Verifica se o logger grava e recupera logs corretamente."""
        entry = logger.info("SmokeTest", "Mensagem de teste unitário", {"key": "val"})
        self.assertIsNotNone(entry.get("id"))
        self.assertEqual(entry.get("level"), "INFO")
        self.assertEqual(entry.get("component"), "SmokeTest")

        logs = logger.get_logs(level="INFO")
        self.assertTrue(any(l.get("message") == "Mensagem de teste unitário" for l in logs))

    def test_02_user_preferences(self):
        """Verifica a extração e persistência de preferências."""
        text = "Eu prefiro usar o VS Code para programar em Python e meu nome é Alex"
        extracted = preference_store.extract_from_text(text)
        self.assertTrue(len(extracted) >= 2)
        
        prefs = preference_store.get_preferences()
        self.assertTrue(any("VS Code" in p for p in prefs))
        self.assertTrue(any("Alex" in p for p in prefs))

    def test_03_clipboard_history(self):
        """Verifica se o histórico da área de transferência é persistido."""
        test_text = f"Texto de teste clipboard {os.urandom(4).hex()}"
        add_clipboard_history(test_text)
        
        history = get_clipboard_history(limit=5)
        self.assertTrue(any(item.get("text") == test_text for item in history))

    def test_04_session_store_history(self):
        """Verifica o armazenamento e recuperação do histórico de sessão."""
        session_id = "test_smoke_session_123"
        history_input = [
            {"role": "user", "content": "Olá Jarvis"},
            {"role": "assistant", "content": "Olá, Sir!"}
        ]
        save_session_history(session_id, history_input)
        retrieved = get_session_history(session_id)
        self.assertEqual(len(retrieved), 2)
        self.assertEqual(retrieved[0]["content"], "Olá Jarvis")

    def test_05_system_media_control(self):
        """Verifica a execução das ações de mídia e telemetria no SystemControlTool."""
        from app.agent.tools.system_control import SystemControlTool
        tool = SystemControlTool()
        res_telemetry = tool.execute({"action": "telemetry"})
        self.assertTrue(res_telemetry.ok)
        
        res_media = tool.execute({"action": "media_play_pause"})
        self.assertTrue(res_media.ok)

    def test_06_wake_word_detector(self):
        """Verifica a inicialização e disponibilidade do WakeWordDetector."""
        from app.services.voice.wake_word import WakeWordDetector
        detector = WakeWordDetector(wake_words={"ei assistente"})
        self.assertTrue(detector.is_available())
        self.assertTrue(detector._matches_wake_word("ei assistente abra o navegador"))

    def test_07_semantic_memory(self):
        """Verifica adição e busca na memória vetorial (ChromaDB)."""
        from app.storage.vector.semantic_memory import SemanticMemory
        sm = SemanticMemory(persist_dir=os.path.join(self.tmp_dir, "test_vector_db"))
        self.assertTrue(sm.is_available())
        
        test_text = f"Memória de teste {os.urandom(4).hex()}"
        added = sm.add_memory("test_collection", test_text)
        self.assertTrue(added)
        
        results = sm.search_memories("test_collection", "teste", n_results=1)
        self.assertTrue(len(results) > 0)

    def test_08_vision_tool(self):
        """Verifica a ferramenta de visão computacional (VisionTool)."""
        from app.agent.tools.vision_tool import VisionTool
        tool = VisionTool()
        self.assertEqual(tool.name, "vision")
        self.assertIn("analyze_screen", tool.parameters["properties"]["action"]["enum"])

    def test_09_browser_agent(self):
        """Verifica a ferramenta do navegador web autônomo (BrowserAgentTool)."""
        from app.agent.tools.browser_agent import BrowserAgentTool
        from app.services.browser_agent import PLAYWRIGHT_AVAILABLE
        self.assertTrue(PLAYWRIGHT_AVAILABLE)
        tool = BrowserAgentTool()
        self.assertEqual(tool.name, "browser_agent")

    def test_10_tts_providers(self):
        """Verifica a arquitetura multi-provider do TTSService (GeminiTTS e EdgeTTS)."""
        from app.services.voice.tts.providers import GeminiTTSProvider, EdgeTTSProvider
        from app.services.voice.tts import TTSService
        from app.services.voice.tts.providers.gemini_tts import _pcm_to_wav

        gemini_provider = GeminiTTSProvider(api_keys=["test_key"], voice="Charon")
        self.assertEqual(gemini_provider.name, "gemini")
        self.assertTrue(gemini_provider.is_available())

        edge_provider = EdgeTTSProvider(voice="pt-BR-AntonioNeural")
        self.assertEqual(edge_provider.name, "edge")
        self.assertTrue(edge_provider.is_available())

        ssml = edge_provider._build_ssml("Teste de fala com vírgula, e ponto final.")
        self.assertIn("<break time='180ms'/>", ssml)
        self.assertIn("<prosody rate='-5%' pitch='-2st'>", ssml)

        # Testa conversor PCM -> WAV
        pcm_dummy = b"\x00\x00" * 100
        wav = _pcm_to_wav(pcm_dummy, sample_rate=24000)
        self.assertTrue(wav.startswith(b"RIFF"))

        # Testa inicialização do TTSService
        service = TTSService(tts_provider="gemini", gemini_api_keys=["test_key"])
        self.assertEqual(len(service.engine._providers), 2)
        self.assertEqual(service.engine._providers[0].name, "gemini")
        self.assertEqual(service.engine._providers[1].name, "edge")

    def test_11_realtime_tool(self):
        """Verifica a ferramenta de dados em tempo real (RealTimeTool e RealTimeService)."""
        from app.agent.tools.realtime_tool import RealTimeTool
        from app.services.realtime import RealTimeService

        tool = RealTimeTool()
        self.assertEqual(tool.name, "realtime")
        self.assertIn("get_weather", tool.parameters["properties"]["action"]["enum"])

        # Testa execução das ações do RealTimeService
        finance = RealTimeService.get_finance()
        self.assertTrue(finance.get("ok", False))
        self.assertIn("USD", finance.get("currencies", {}))

        weather = RealTimeService.get_weather("Sertãozinho")
        self.assertTrue(weather.get("ok", False))
        city_name = weather.get("city", "")
        self.assertTrue(
            "Sertaozinho" in city_name or "Sertãozinho" in city_name or "Sertaozinho" in city_name.encode('ascii', errors='replace').decode(),
            msg=f"City name '{city_name}' doesn't match Sertãozinho"
        )

        tool_res = tool.execute({"action": "get_weather", "city": "Sertãozinho"})
        self.assertTrue(tool_res.ok)
        self.assertTrue(
            "Sertaozinho" in tool_res.message or "Sertãozinho" in tool_res.message,
            msg=f"Message '{tool_res.message}' doesn't contain city name"
        )

        holidays = RealTimeService.get_holidays(2026)
        self.assertTrue(holidays.get("ok", False))
        self.assertTrue(len(holidays.get("holidays", [])) > 0)

    def test_12_proactive_agent(self):
        """Verifica a ferramenta proativa (ProactiveAgentTool e ProactiveService)."""
        from app.agent.tools.proactive_agent import ProactiveAgentTool
        from app.services.proactive import ProactiveService

        service = ProactiveService(config_path=os.path.join(self.tmp_dir, "test_proactive_config.json"))
        tool = ProactiveAgentTool(service=service)
        self.assertEqual(tool.name, "proactive_agent")

        # Testa adição de lembrete
        res = tool.execute({"action": "add_reminder", "reminder_message": "Tomar remédio", "reminder_time": "+5m"})
        self.assertTrue(res.ok)
        self.assertIn("Tomar remédio", res.message)

        # Testa atualização de briefing
        cfg_res = tool.execute({"action": "configure_briefing", "custom_instructions": "Não fale sobre o clima de manhã"})
        self.assertTrue(cfg_res.ok)
        self.assertEqual(service.get_config()["custom_instructions"], "Não fale sobre o clima de manhã")

        # Limpa arquivo temporário de teste
        if service.config_path.exists():
            service.config_path.unlink()

    def test_13_system_tray(self):
        """Verifica o serviço de System Tray e Boot Automático (TrayService e BootService)."""
        from app.services.tray import TrayService, BootService
        from app.agent.tools.system_tray_tool import SystemTrayTool

        # Valida BootService (leitura do registry sem alterar)
        status = BootService.is_enabled()
        self.assertIsInstance(status, bool)

        # Valida tool (sem alterar o registry — só chama status)
        tool = SystemTrayTool()
        self.assertEqual(tool.name, "system_tray")
        res = tool.execute({"action": "status"})
        self.assertTrue(res.ok)
        self.assertIn("boot_enabled", res.data)

        # Valida TrayService (apenas instanciação, sem iniciar thread de tray)
        tray = TrayService(panel_url="http://127.0.0.1:8000")
        img = tray._make_icon_image()
        self.assertIsNotNone(img)

if __name__ == "__main__":
    print("[Smoke Test] Executando Smoke Tests do Jarvis...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJarvisSmoke)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
