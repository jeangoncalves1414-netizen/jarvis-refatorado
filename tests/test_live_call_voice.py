"""Testes unitários automatizados para a experiência de voz conversacional (Live Call).

Cobre:
1. Sanitização robusta de texto para fala (remoção de preâmbulos de ferramentas, links, markdown, bullets).
2. Seleção e progressão de fillers contextuais (pesquisa, raciocínio e progressão para operações longas).
3. Detecção precisa de comandos de cancelamento ativo por voz (ex: "para de falar", "cancela", "para de pesquisar").
4. Alternância e detecção de modo silencioso (progress narration silenciada).
5. Interrupção imediata (barge-in) e abort callbacks.
6. Ação de cancelamento ativo e parada imediata com feedback por voz.
7. Montagem e refinamento de Context Stitching pós-interrupção.
"""
from __future__ import annotations

import unittest
from app.services.voice_call import (
    VoiceCallEngine,
    CallState,
    SEARCH_FILLERS,
    THINKING_FILLERS,
    PROGRESSION_FILLERS,
    is_cancel_command,
    detect_silence_command,
    build_context_stitching_prompt,
    sanitize_speech_text,
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
    # 1. Sanitização de texto para TTS (Voice Call Sanitization)
    # -------------------------------------------------------------------------
    def test_sanitize_speech_text_reported_tool_preambles_and_links(self):
        """Valida a resolução do caso reportado pelo usuário com links e cabeçalhos brutos."""
        raw = (
            "Resultados das ferramentas: Resultado de web_search: Resultados para senhor RO notícias: "
            "1. Senhor - Dicio Link: https://www.dicio.com.br/senhor/ "
            "2. Senhor - Wikipedia Link: https://pt.wikipedia.org/wiki/Senhor"
        )
        cleaned = sanitize_speech_text(raw)

        # Não deve conter preâmbulos brutos
        self.assertNotIn("Resultados das ferramentas", cleaned)
        self.assertNotIn("Resultado de web_search", cleaned)
        # Não deve soletrar links/URLs
        self.assertNotIn("Link:", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("www.dicio.com.br", cleaned)
        # Deve preservar o conteúdo informativo
        self.assertIn("Resultados para senhor RO notícias", cleaned)
        self.assertIn("Senhor - Dicio", cleaned)
        self.assertIn("Senhor - Wikipedia", cleaned)

    def test_sanitize_speech_text_tool_preambles_and_browser(self):
        """Verifica a remoção de preâmbulos de navegador, comandos e logs de terminal."""
        inputs = [
            "Navegador aberto na URL: https://noticias.globo.com - O dia amanheceu ensolarado.",
            "Saída do terminal: Processo concluído com êxito.",
            "Comando executado: ls -la. A pasta possui três arquivos.",
            "Ferramenta executada: [tool:open_windows_app:chrome] Google Chrome iniciado.",
            "Página aberta em: https://github.com/trending - Principais repositórios.",
        ]
        for item in inputs:
            cleaned = sanitize_speech_text(item)
            self.assertNotIn("https://", cleaned)
            self.assertNotIn("[tool:", cleaned)
            self.assertNotIn("Navegador aberto na URL", cleaned)
            self.assertNotIn("Saída do terminal:", cleaned)
            self.assertNotIn("Comando executado:", cleaned)
            self.assertNotIn("Ferramenta executada:", cleaned)
            self.assertNotIn("Página aberta em:", cleaned)

    def test_sanitize_speech_text_markdown_and_citations(self):
        """Remove markdown excessivo, links formatados, citações e bullets repetitivos."""
        raw = (
            "# Título Principal\n\n"
            "Conforme verificado em [portal de notícias](https://noticias.exemplo.com) [1], "
            "o **PIB** subiu *0.8%* no `último trimestre`.\n"
            "- Item A\n"
            "- Item B\n"
            "1. Primeiro passo\n"
            "2. Segundo passo"
        )
        cleaned = sanitize_speech_text(raw)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertNotIn("[1]", cleaned)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("- Item", cleaned)
        self.assertIn("portal de notícias", cleaned)
        self.assertIn("PIB subiu 0.8% no último trimestre", cleaned)
        self.assertIn("Primeiro passo", cleaned)
        self.assertIn("Segundo passo", cleaned)

    def test_sanitize_speech_text_clean_conversational_flow(self):
        """Verifica se pontuação órfã ou espaços múltiplos são corrigidos com fluidez."""
        raw = "   Resultado da pesquisa:   :  Previsão de chuva para amanhã.   Fonte: https://tempo.com   "
        cleaned = sanitize_speech_text(raw)
        self.assertEqual(cleaned, "Previsão de chuva para amanhã.")

    def test_sanitize_speech_text_never_spells_urls(self):
        """Garante que URLs brutas (https, http, www) são completamente removidas para não serem soletradas."""
        raw = "Acesse https://noticias.uol.com.br/hoje ou www.globo.com para mais detalhes."
        cleaned = sanitize_speech_text(raw)
        self.assertNotIn("https://", cleaned)
        self.assertNotIn("http://", cleaned)
        self.assertNotIn("www.", cleaned)
        self.assertNotIn("uol.com.br", cleaned)
        self.assertNotIn("globo.com", cleaned)
        self.assertIn("Acesse ou para mais detalhes.", cleaned)

    def test_sanitize_speech_text_removes_all_markdown(self):
        """Garante a remoção completa de marcadores de negrito, itálico, títulos e crases."""
        raw = "### Título da Notícia\nO modelo obteve **98% de precisão** e *ótima acurácia* no script `run.py`."
        cleaned = sanitize_speech_text(raw)
        self.assertNotIn("#", cleaned)
        self.assertNotIn("**", cleaned)
        self.assertNotIn("*", cleaned)
        self.assertNotIn("`", cleaned)
        self.assertIn("Título da Notícia", cleaned)
        self.assertIn("98% de precisão", cleaned)
        self.assertIn("ótima acurácia", cleaned)
        self.assertIn("no script run.py", cleaned)

    # -------------------------------------------------------------------------
    # 2. Fillers contextuais e progressão em operações longas
    # -------------------------------------------------------------------------
    def test_filler_lists_content(self):
        """Verifica se as listas de fillers contêm as frases esperadas em pt-BR."""
        self.assertIn("Procurando na web...", SEARCH_FILLERS)
        self.assertIn("Deixa eu conferir as fontes...", SEARCH_FILLERS)
        self.assertIn("Dando uma olhada nos sites...", SEARCH_FILLERS)

        self.assertIn("Só um momento...", THINKING_FILLERS)
        self.assertIn("Hm, analisando aqui...", THINKING_FILLERS)
        self.assertIn("Deixa eu pensar bem nisso...", THINKING_FILLERS)

        self.assertIn("Ainda estou consultando as informações...", PROGRESSION_FILLERS)
        self.assertIn("Só mais um instante...", PROGRESSION_FILLERS)
        self.assertIn("Cruzando os dados que encontrei...", PROGRESSION_FILLERS)
        self.assertIn("Ainda processando os resultados...", PROGRESSION_FILLERS)

    def test_filler_selection_and_progression_cycling(self):
        """Testa seleção contextual por categoria (search, thinking e progression)."""
        # Categoria search
        filler_search_0 = self.engine.get_filler("search", self.session_id, index=0)
        self.assertEqual(filler_search_0, SEARCH_FILLERS[0])

        filler_search_1 = self.engine.get_filler("web", self.session_id, index=1)
        self.assertEqual(filler_search_1, SEARCH_FILLERS[1])

        # Categoria thinking
        filler_think_0 = self.engine.get_filler("thinking", self.session_id, index=0)
        self.assertEqual(filler_think_0, THINKING_FILLERS[0])

        # Categoria progressão (operações longas > 3.5s)
        filler_prog_0 = self.engine.get_filler("progress", self.session_id, index=0)
        self.assertEqual(filler_prog_0, PROGRESSION_FILLERS[0])

        filler_prog_1 = self.engine.get_filler("progression", self.session_id, index=1)
        self.assertEqual(filler_prog_1, PROGRESSION_FILLERS[1])

        # Ciclo automático de progressão pela sessão
        p1 = self.engine.get_filler("progression", self.session_id)
        p2 = self.engine.get_filler("progression", self.session_id)
        self.assertEqual(p1, PROGRESSION_FILLERS[0])
        self.assertEqual(p2, PROGRESSION_FILLERS[1])

    def test_silent_mode_suppresses_all_fillers(self):
        """No modo silencioso ativado, nenhum filler (inclusive progressão) deve ser emitido."""
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
        self.assertEqual(self.engine.get_filler("progress", self.session_id), "")

        # Alterna de volta
        res_toggle = self.engine.toggle_silent_mode(self.session_id)
        self.assertFalse(res_toggle["silent_mode"])
        self.assertFalse(self.engine.is_silent_mode(self.session_id))
        self.assertTrue(bool(self.engine.get_filler("progress", self.session_id)))

    # -------------------------------------------------------------------------
    # 3. Detecção de Comandos de Cancelamento Ativo por Voz
    # -------------------------------------------------------------------------
    def test_cancel_command_detection_positive(self):
        """Verifica frases que devem ser identificadas como cancelamento ativo."""
        cancel_phrases = [
            "cancela",
            "cancelar",
            "para",
            "parar",
            "para de falar",
            "pare de falar",
            "para de pesquisar",
            "pare de pesquisar",
            "deixa pra lá",
            "deixa pra la",
            "cancela a pesquisa",
            "cancela isso",
            "para tudo",
            "para agora",
            "chega",
            "silêncio",
            "Jarvis, cancela",
            "Jarvis, para de falar",
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
            "fale mais sobre física quântica",
        ]
        for phrase in normal_phrases:
            with self.subTest(phrase=phrase):
                self.assertFalse(
                    is_cancel_command(phrase),
                    f"Frase NÃO deveria ser identificada como cancelamento: '{phrase}'"
                )

    # -------------------------------------------------------------------------
    # 4. Detecção de Comandos de Modo Silencioso
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
    # 5. Context Stitching Refinado pós-interrupção (Barge-In)
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

    def test_interrupt_call_preserves_interrupted_text_and_triggers_callbacks(self):
        """Verifica se interrupt_call armazena o trecho interrompido e aciona callbacks de abort."""
        interrupted = "Estou consultando a base de dados climáticos..."
        callback_fired = []

        self.engine.register_abort_callback(self.session_id, lambda: callback_fired.append(True))
        res = self.engine.interrupt_call(self.session_id, interrupted_text=interrupted)
        self.assertTrue(res["ok"])
        self.assertTrue(res["interrupted"])
        self.assertEqual(res["interrupted_text"], interrupted)
        self.assertEqual(callback_fired, [True])

        status = self.engine.get_session_status(self.session_id)
        self.assertEqual(status["last_interrupted_text"], interrupted)

    # -------------------------------------------------------------------------
    # 6. Cancelamento ativo de ação e parada imediata
    # -------------------------------------------------------------------------
    def test_cancel_active_action_and_abort_callbacks(self):
        """Verifica cancelamento de ação, confirmação por voz e execução de callbacks."""
        self.session.state = CallState.THINKING
        callback_called = []
        self.engine.register_abort_callback(self.session_id, lambda: callback_called.append("cancelled"))

        res = self.engine.cancel_active_action(self.session_id)
        self.assertTrue(res["ok"])
        self.assertTrue(res["cancelled"])
        self.assertEqual(res["confirmation"], "Cancelado. O que você gostaria de fazer agora?")
        self.assertEqual(self.session.state, CallState.LISTENING)
        self.assertTrue(self.session.is_cancelled)
        self.assertEqual(callback_called, ["cancelled"])


if __name__ == "__main__":
    unittest.main()
