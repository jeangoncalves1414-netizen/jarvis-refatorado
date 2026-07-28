"""
Suíte de Testes de Estresse & Edge Cases do Jarvis.
Testa concorrência, inputs malformados, tratamento de exceções e resiliência das Fases 10-13.
Executar com: python tests/stress_test.py
"""

import unittest
import os
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.voice.tts.cleaner import strip_text_for_speech
from app.services.voice.tts.prefetch import split_text_for_tts
from app.services.voice.tts.providers.gemini_tts import GeminiTTSProvider, _pcm_to_wav
from app.services.voice.tts.providers.edge_tts_provider import EdgeTTSProvider
from app.services.realtime import RealTimeService
from app.services.proactive import ProactiveService, ProactiveDaemon
from app.services.tray import BootService, TrayService
from app.agent.tools.registry import ToolRegistry


class TestJarvisStressAndEdgeCases(unittest.TestCase):

    def test_01_tts_cleaner_edge_cases(self):
        """Testa o limpador de texto de TTS com entradas extremas (código, emojis, markdown, html)."""
        # Entrada vazia ou espaços
        self.assertEqual(strip_text_for_speech(""), "")
        self.assertEqual(strip_text_for_speech("   \n\t  "), "")

        # Markdown e links
        text_md = "# Título\nVeja no [link](https://example.com) o `código` com **negrito** e *itálico*."
        cleaned = strip_text_for_speech(text_md)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)

        # Código fonte longo
        code_input = "def foo():\n    return {'a': 1, 'b': 2}\nprint('Olá!')"
        cleaned_code = strip_text_for_speech(code_input)
        self.assertIsInstance(cleaned_code, str)

        # Emojis e caracteres unicodes
        emoji_input = "Olá mundo! 🚀🤖🔥 Exemplo de texto em português."
        cleaned_emoji = strip_text_for_speech(emoji_input)
        self.assertIn("Olá mundo", cleaned_emoji)

    def test_02_tts_prefetch_split_extreme(self):
        """Testa o fatiador de texto com textos gigantes (10.000+ caracteres)."""
        large_text = "Esta é uma frase de teste longa. " * 500  # ~16.000 caracteres
        chunks = split_text_for_tts(large_text, max_chars=1000)
        self.assertTrue(len(chunks) > 10)
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 1200)  # Tolerância de quebra de frase

    def test_03_gemini_tts_provider_resilience(self):
        """Testa o GeminiTTSProvider sob rotação de chaves e entradas nulas."""
        # Sem chaves
        p_no_key = GeminiTTSProvider(api_keys=[], voice="Charon")
        self.assertFalse(p_no_key.is_available())
        self.assertIsNone(p_no_key.generate("teste"))

        # Com 1 chave
        p_single = GeminiTTSProvider(api_keys=["fake_key_123"], voice="Charon")
        self.assertTrue(p_single.is_available())

        # Teste de rotação com _next_key
        k1 = p_single._current_key
        k2 = p_single._next_key()
        self.assertEqual(k1, k2)  # Deve repetir k1 se só tiver 1 chave

        # Conversor PCM -> WAV com 0 bytes
        wav_empty = _pcm_to_wav(b"", sample_rate=24000)
        self.assertTrue(wav_empty.startswith(b"RIFF"))

    def test_04_edge_tts_provider_ssml_escaping(self):
        """Testa escape de XML e pontuação no SSML do Edge TTS."""
        provider = EdgeTTSProvider()
        
        # Testa com caracteres de injeção XML (<, >, &, ")
        raw_text = "Jarvis & Cia <teste> \"aspas\" e pontuação... sim!"
        ssml = provider._build_ssml(raw_text)

        self.assertNotIn("<teste>", ssml)
        self.assertIn("&amp;", ssml)
        self.assertIn("&lt;teste&gt;", ssml)
        self.assertIn("&quot;aspas&quot;", ssml)
        self.assertIn("<break time='480ms'/>", ssml)

    def test_05_realtime_service_robustness(self):
        """Testa resiliência do RealTimeService contra nomes de cidade estranhos e datas futuras."""
        # Cidade com caracteres estranhos
        w1 = RealTimeService.get_weather("!@#$%^&*()")
        self.assertIsInstance(w1, dict)
        self.assertIn("ok", w1)

        # Cidade vazia (deve buscar localização atual)
        w2 = RealTimeService.get_weather("")
        self.assertIsInstance(w2, dict)

        # Feriados de ano distante (ex: 2099)
        h2099 = RealTimeService.get_holidays(2099)
        self.assertIsInstance(h2099, dict)

        # Cotações (deve ser dicionário válido)
        fin = RealTimeService.get_finance()
        self.assertIsInstance(fin, dict)
        self.assertTrue(fin.get("ok", False))

    def test_06_proactive_service_thread_concurrency(self):
        """Testa acessos concorrentes simultâneos ao ProactiveService com 10 threads."""
        test_file = Path("data/test_stress_proactive.json")
        if test_file.exists():
            test_file.unlink()

        service = ProactiveService(config_path=test_file)
        errors = []

        def worker(thread_idx: int):
            try:
                for i in range(10):
                    service.add_reminder(f"Lembrete T{thread_idx}_{i}", f"+{i+1}m")
                    service.update_briefing_config(custom_instructions=f"Thread {thread_idx} ciclo {i}")
                    service.get_config()
                    service.get_pending_reminders()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Erros durante acesso concorrente: {errors}")
        
        # Verifica se todos os 100 lembretes foram registrados sem perda
        reminders = service.get_pending_reminders()
        self.assertEqual(len(reminders), 100)

        # Limpeza
        if test_file.exists():
            test_file.unlink()

    def test_07_proactive_daemon_rapid_start_stop(self):
        """Testa ciclo rápido de inicialização e parada do ProactiveDaemon."""
        test_file = Path("data/test_daemon_proactive.json")
        if test_file.exists():
            test_file.unlink()

        service = ProactiveService(config_path=test_file)
        daemon = ProactiveDaemon(proactive_service=service, interval_seconds=1)
        
        daemon.start()
        time.sleep(0.2)
        daemon.stop()
        daemon.join(timeout=5.0)

        self.assertFalse(daemon.is_alive(), "Daemon deve ter sido finalizado após stop().")


        if test_file.exists():
            test_file.unlink()

    def test_08_system_tray_and_boot_resilience(self):
        """Testa funções do BootService e TrayService sob estresse."""
        # BootService status e caminhos
        cmd = BootService._get_startup_command()
        self.assertIn("pythonw", cmd.lower())
        self.assertIn("run_jarvis.pyw", cmd)

        # TrayService ícone PIL
        tray = TrayService()
        img = tray._make_icon_image()
        self.assertIsNotNone(img)
        self.assertEqual(img.size, (64, 64))

    def test_09_all_registered_tools_invalid_args_handling(self):
        """Testa se TODAS as ferramentas registradas no ToolRegistry lidam graciosamente com argumentos inválidos/vazios."""
        registry = ToolRegistry()
        tools = registry.tools
        self.assertTrue(len(tools) >= 15)


        for name, tool in tools.items():
            # Executa com dicionário vazio ou parâmetros aleatórios
            try:
                result = tool.execute({})
                self.assertIsNotNone(result)
                self.assertIsInstance(result.ok, bool)
            except Exception as e:
                self.fail(f"Ferramenta '{name}' lançou exceção não tratada ao receber argumento vazio: {e}")


if __name__ == "__main__":
    print("[Stress Test] Executando Suíte de Testes de Estresse do Jarvis...")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestJarvisStressAndEdgeCases)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
