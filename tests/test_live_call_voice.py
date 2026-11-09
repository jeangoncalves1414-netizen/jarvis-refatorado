"""Testes unitários automatizados para a experiência de voz conversacional (Live Call).

Cobre:
1. Seleção e ciclo de fillers contextuais (pesquisa e raciocínio/thinking) e respeito ao silent_mode.
2. Detecção precisa de comandos de cancelamento ativo por voz (ex: "cancela", "para de pesquisar").
3. Alternância e detecção de modo silencioso (progress narration silenciada).
4. Montagem e refinamento de Context Stitching pós-interrupção (barge-in).
5. Ação de cancelamento e preservação de trecho interrompido na sessão.
"""
from __future__ import annotations

import unittest
from app.services.voice_call import (
    VoiceCallEngine,
    CallState,
    SEARCH_FILLERS,
    THINKING_FILLERS,
    is_cancel_command,
    detect_silence_command,
    build_context_stitching_prompt,
)


class TestLiveCallConversationalVoice(unittest.TestCase):

    def setUp(self):
        self.engine = VoiceCallEngine()
        self.session_id = "test_call_voice_001"
        self.session = self.engine.start_call(self.session_id)

    def tearDown(self):
        if self.session_id in self.engine.active_sessions:
            self.engine.end_call(self.session_id)

    # -------------------------------------------------------------------------
    # 1. Fillers contextuais e modo silencioso
    # -------------------------------------------------------------------------
    def test_filler_lists_content(self):
        """Verifica se as listas de fillers contêm as frases esperadas em pt-BR."""
        self.assertIn("Procurando na web...", SEARCH_FILLERS)
        self.assertIn("Deixa eu conferir as fontes...", SEARCH_FILLERS)
        self.assertIn("Dando uma olhada nos sites...", SEARCH_FILLERS)

        self.assertIn("Só um momento...", THINKING_FILLERS)
        self.assertIn("Hm, analisando aqui...", THINKING_FILLERS)
        self.assertIn("Deixa eu pensar bem nisso...", THINKING_FILLERS)

    def test_filler_selection_and_cycling(self):
        """Testa seleção contextual por categoria e rotação sequencial."""
        # Categoria search
        filler_search_0 = self.engine.get_filler("search", self.session_id, index=0)
        self.assertEqual(filler_search_0, SEARCH_FILLERS[0])

        filler_search_1 = self.engine.get_filler("web", self.session_id, index=1)
        self.assertEqual(filler_search_1, SEARCH_FILLERS[1])

        # Categoria thinking
        filler_think_0 = self.engine.get_filler("thinking", self.session_id, index=0)
        self.assertEqual(filler_think_0, THINKING_FILLERS[0])

        filler_think_1 = self.engine.get_filler("reasoning", self.session_id, index=1)
        self.assertEqual(filler_think_1, THINKING_FILLERS[1])

    def test_silent_mode_suppresses_fillers(self):
        """No modo silencioso ativado, fillers devem retornar string vazia."""
        # Inicialmente silent_mode é falso
        self.assertFalse(self.engine.is_silent_mode(self.session_id))
        self.assertTrue(bool(self.engine.get_filler("search", self.session_id)))

        # Ativa silent mode
        res = self.engine.set_silent_mode(self.session_id, True)
        self.assertTrue(res["ok"])
        self.assertTrue(res["silent_mode"])
        self.assertTrue(self.engine.is_silent_mode(self.session_id))

        # Fillers não devem ser emitidos
        self.assertEqual(self.engine.get_filler("search", self.session_id), "")
        self.assertEqual(self.engine.get_filler("thinking", self.session_id), "")

        # Alterna de volta
        res_toggle = self.engine.toggle_silent_mode(self.session_id)
        self.assertFalse(res_toggle["silent_mode"])
        self.assertFalse(self.engine.is_silent_mode(self.session_id))
        self.assertTrue(bool(self.engine.get_filler("search", self.session_id)))

    # -------------------------------------------------------------------------
    # 2. Detecção de Comandos de Cancelamento Ativo por Voz
    # -------------------------------------------------------------------------
    def test_cancel_command_detection_positive(self):
        """Verifica frases que devem ser identificadas como cancelamento ativo."""
        cancel_phrases = [
            "cancela",
            "cancelar",
            "para",
            "parar",
            "deixa pra lá",
            "deixa pra la",
            "cancela a pesquisa",
            "para de pesquisar",
            "cancela isso",
            "para tudo",
            "Jarvis, cancela",
            "Jarvis, para de pesquisar",
            "jarvis deixa pra lá",
            "aborta",
            "abortar",
            "cancela!",
            "para.",
        ]
        for phrase in cancel_phrases:
            with self.subTest(phrase=phrase):
                self.assertTrue(
                    is_cancel_command(phrase),
                    f"Frase deveria ser identificada como cancelamento: '{phrase}'"
                )

    def test_cancel_command_detection_negative(self):
        """Verifica frases comuns ou perguntas que NÃO devem ser canceladas."""
        normal_phrases = [
            "qual a previsão do tempo para amanhã?",
            "não quero cancelar minha reserva",
            "o que é um paraquedas?",
            "pesquise notícias sobre tecnologia",
            "como fazer um bolo de chocolate",
            "para onde vão os pássaros no inverno?",
        ]
        for phrase in normal_phrases:
            with self.subTest(phrase=phrase):
                self.assertFalse(
                    is_cancel_command(phrase),
                    f"Frase NÃO deveria ser identificada como cancelamento: '{phrase}'"
                )

    # -------------------------------------------------------------------------
    # 3. Detecção de Comandos de Modo Silencioso
    # -------------------------------------------------------------------------
    def test_silence_command_detection(self):
        """Testa frases de ativação e desativação de silêncio na narração."""
        enable_phrases = [
            "não precisa narrar",
            "pesquise em silêncio",
            "pesquisa em silêncio",
            "não precisa falar nada enquanto pesquisa",
            "não precisa falar nada",
            "ative o modo silencioso",
            "fique em silêncio",
            "sem narrar",
        ]
        for phrase in enable_phrases:
            with self.subTest(phrase=phrase):
                is_cmd, enable = detect_silence_command(phrase)
                self.assertTrue(is_cmd, f"Deveria detectar comando em: '{phrase}'")
                self.assertTrue(enable, f"Deveria ser ativação de silêncio em: '{phrase}'")

        disable_phrases = [
            "pode narrar",
            "pode falar",
            "desative o modo silencioso",
            "sai do modo silencioso",
            "desativar silêncio",
        ]
        for phrase in disable_phrases:
            with self.subTest(phrase=phrase):
                is_cmd, enable = detect_silence_command(phrase)
                self.assertTrue(is_cmd, f"Deveria detectar comando em: '{phrase}'")
                self.assertFalse(enable, f"Deveria ser desativação de silêncio em: '{phrase}'")

        # Frase qualquer sem comando de silêncio
        is_cmd, _ = detect_silence_command("qual é a capital da França?")
        self.assertFalse(is_cmd)

    # -------------------------------------------------------------------------
    # 4. Context Stitching Refinado pós-interrupção (Barge-In)
    # -------------------------------------------------------------------------
    def test_build_context_stitching_prompt(self):
        """Verifica a montagem exata do prompt refinado de context stitching."""
        cut_off = "O sistema solar possui oito planetas reconhecidos pela União Astronômica Internacional, sendo o maior"
        user_speech = "Espera, e Plutão? Ele ainda é planeta?"

        prompt = build_context_stitching_prompt(cut_off, user_speech)

        expected = (
            f'[Contexto da Interrupção: Você estava dizendo: "{cut_off}". '
            f'O usuário te interrompeu dizendo: "{user_speech}". '
            'Responda de forma ágil e coesa, incorporando a observação ao que já estava sendo discutido sem repetir tudo do zero.]'
        )
        self.assertEqual(prompt, expected)

    def test_interrupt_call_preserves_interrupted_text(self):
        """Verifica se interrupt_call armazena o trecho interrompido na sessão."""
        interrupted = "Estou consultando a base de dados climáticos..."
        res = self.engine.interrupt_call(self.session_id, interrupted_text=interrupted)
        self.assertTrue(res["ok"])
        self.assertTrue(res["interrupted"])
        self.assertEqual(res["interrupted_text"], interrupted)

        status = self.engine.get_session_status(self.session_id)
        self.assertEqual(status["last_interrupted_text"], interrupted)

    # -------------------------------------------------------------------------
    # 5. Cancelamento ativo de ação
    # -------------------------------------------------------------------------
    def test_cancel_active_action(self):
        """Verifica resposta de cancelamento de ação e confirmação por voz."""
        self.session.state = CallState.THINKING
        res = self.engine.cancel_active_action(self.session_id)
        self.assertTrue(res["ok"])
        self.assertTrue(res["cancelled"])
        self.assertEqual(res["confirmation"], "Cancelado. O que você gostaria de fazer agora?")
        self.assertEqual(self.session.state, CallState.LISTENING)


if __name__ == "__main__":
    unittest.main()
