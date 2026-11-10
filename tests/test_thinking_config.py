"""
Testes unitários para validação da configuração de Ultra-Thinking (thinking_budget)
e injeção de prompts dos modos especializados no AgentOrchestrator.
"""

from unittest.mock import MagicMock, patch
import pytest

from google.genai import types
from app.services.llm import LLMService
from app.agent.orchestrator import AgentOrchestrator


class DummySettings:
    llm_provider = "gemini"
    llm_model = "gemini-2.5-flash"
    gemini_api_key = "test_gemini_key_123"
    gemini_api_keys = ["test_gemini_key_123"]


class TestGeminiThinkingConfig:
    """Valida a configuração de thinking_budget=4096 no LLMService."""

    def test_thinking_config_budget_in_planning_mode(self):
        settings = DummySettings()
        llm = LLMService(settings=settings)

        # Mock do genai.Client
        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_client.models.generate_content_stream.return_value = mock_stream
        # Simula gerador vazio
        mock_stream.__iter__.return_value = []

        with patch("google.genai.Client", return_value=mock_client):
            # Chamada com mode="planning"
            llm.chat_with_functions_stream(
                system_instruction="Teste de sistema",
                messages=[{"role": "user", "content": "Raciocine sobre este problema"}],
                mode="planning",
            )

            assert mock_client.models.generate_content_stream.called
            call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
            config = call_kwargs.get("config")
            assert config is not None
            assert config.thinking_config is not None
            assert config.thinking_config.include_thoughts is True
            assert config.thinking_config.thinking_budget == 4096

    def test_thinking_config_budget_in_thinking_mode(self):
        settings = DummySettings()
        llm = LLMService(settings=settings)

        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_client.models.generate_content_stream.return_value = mock_stream
        mock_stream.__iter__.return_value = []

        with patch("google.genai.Client", return_value=mock_client):
            # Chamada com mode="thinking"
            llm.chat_with_functions_stream(
                system_instruction="Teste de sistema",
                messages=[{"role": "user", "content": "Analise logicamente"}],
                mode="thinking",
            )

            assert mock_client.models.generate_content_stream.called
            call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
            config = call_kwargs.get("config")
            assert config is not None
            assert config.thinking_config is not None
            assert config.thinking_config.include_thoughts is True
            assert config.thinking_config.thinking_budget == 4096

    def test_thinking_config_budget_not_forced_in_general_mode(self):
        settings = DummySettings()
        llm = LLMService(settings=settings)

        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_client.models.generate_content_stream.return_value = mock_stream
        mock_stream.__iter__.return_value = []

        with patch("google.genai.Client", return_value=mock_client):
            # Chamada em modo geral
            llm.chat_with_functions_stream(
                system_instruction="Teste de sistema",
                messages=[{"role": "user", "content": "Olá"}],
                mode="general",
            )

            assert mock_client.models.generate_content_stream.called
            call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
            config = call_kwargs.get("config")
            assert config is not None
            assert config.thinking_config is not None
            assert config.thinking_config.include_thoughts is True
            # Budget não deve ser 4096 para modo geral
            assert config.thinking_config.thinking_budget is None

    def test_generate_stream_thinking_budget(self):
        settings = DummySettings()
        llm = LLMService(settings=settings)

        mock_client = MagicMock()
        mock_stream = MagicMock()
        mock_client.models.generate_content_stream.return_value = mock_stream
        mock_stream.__iter__.return_value = []

        with patch("google.genai.Client", return_value=mock_client):
            llm.generate_stream(
                contents=[{"role": "user", "parts": [{"text": "Dilema"}]}],
                mode="thinking",
            )

            assert mock_client.models.generate_content_stream.called
            call_kwargs = mock_client.models.generate_content_stream.call_args.kwargs
            config = call_kwargs.get("config")
            assert config is not None
            assert config.thinking_config.thinking_budget == 4096

    def test_on_reasoning_forwards_thought_parts(self):
        settings = DummySettings()
        llm = LLMService(settings=settings)

        # Simula resposta em streaming com parte de pensamento (thought=True)
        thought_part = MagicMock()
        thought_part.thought = True
        thought_part.text = "Pensando sobre as premissas da questão..."
        candidate = MagicMock()
        candidate.content.parts = [thought_part]
        chunk = MagicMock()
        chunk.text = None
        chunk.candidates = [candidate]

        mock_client = MagicMock()
        mock_client.models.generate_content_stream.return_value = [chunk]

        captured_thoughts = []

        def on_reasoning(thought_text):
            captured_thoughts.append(thought_text)

        with patch("google.genai.Client", return_value=mock_client):
            llm.chat_with_functions_stream(
                system_instruction="Sistema",
                messages=[{"role": "user", "content": "Dilema"}],
                on_reasoning=on_reasoning,
                mode="thinking",
            )

        assert len(captured_thoughts) == 1
        assert captured_thoughts[0] == "Pensando sobre as premissas da questão..."


class TestOrchestratorModePrompts:
    """Valida a injeção dos prompts específicos de cada modo no AgentOrchestrator."""

    @pytest.fixture
    def mock_orchestrator(self, tmp_path, monkeypatch):
        from app.storage.action_store import ActionStore
        test_store = ActionStore(tmp_path / "runs.jsonl")
        monkeypatch.setattr("app.storage.action_store.action_store", test_store)

        settings = DummySettings()
        mock_llm = MagicMock()
        mock_llm.get_active_provider.return_value = "gemini"
        mock_llm._api_key_for.return_value = "test_key"
        mock_llm.chat_with_functions_stream.return_value = "Resposta simulada"

        orchestrator = AgentOrchestrator(
            settings=settings,
            llm_service=mock_llm,
        )
        return orchestrator, mock_llm

    def test_planning_mode_injects_ultra_thinking_prompt(self, mock_orchestrator):
        orchestrator, mock_llm = mock_orchestrator

        orchestrator.handle_request("Dilema ético", mode="planning")

        assert mock_llm.chat_with_functions_stream.called
        call_kwargs = mock_llm.chat_with_functions_stream.call_args.kwargs
        system_instruction = call_kwargs.get("system_instruction", "")

        assert "MODO DE RACIOCÍNIO ANALÍTICO PROFUNDO (ULTRA-THINKING)" in system_instruction
        assert "1. Decomposição de premissas" in system_instruction
        assert "2. Casos extremos e falhas potenciais" in system_instruction
        assert "3. Avaliação de alternativas e trade-offs" in system_instruction
        assert "4. Síntese e decisão final" in system_instruction
        # Garante que a antiga instrução restritiva NÃO está presente
        assert "Não exponha raciocínio interno" not in system_instruction
        assert call_kwargs.get("mode") == "planning"

    def test_thinking_mode_injects_ultra_thinking_prompt(self, mock_orchestrator):
        orchestrator, mock_llm = mock_orchestrator

        orchestrator.handle_request("Dilema ético", mode="thinking")

        assert mock_llm.chat_with_functions_stream.called
        call_kwargs = mock_llm.chat_with_functions_stream.call_args.kwargs
        system_instruction = call_kwargs.get("system_instruction", "")

        assert "MODO DE RACIOCÍNIO ANALÍTICO PROFUNDO (ULTRA-THINKING)" in system_instruction
        assert "1. Decomposição de premissas" in system_instruction
        assert call_kwargs.get("mode") == "thinking"

    def test_coder_mode_injects_coder_pro_prompt(self, mock_orchestrator):
        orchestrator, mock_llm = mock_orchestrator

        orchestrator.handle_request("Escreva uma classe Python", mode="coder")

        assert mock_llm.chat_with_functions_stream.called
        call_kwargs = mock_llm.chat_with_functions_stream.call_args.kwargs
        system_instruction = call_kwargs.get("system_instruction", "")

        assert "MODO CODER PRO" in system_instruction
        assert "Tipagem estrita e completa" in system_instruction
        assert "Tratamento robusto de exceções" in system_instruction
        assert "NUNCA use placeholders como 'TODO'" in system_instruction
        assert call_kwargs.get("mode") == "coder"

    def test_lifeos_mode_injects_agile_secretary_prompt(self, mock_orchestrator):
        orchestrator, mock_llm = mock_orchestrator

        orchestrator.handle_request("Bebi 500ml de água", mode="lifeos")

        assert mock_llm.chat_with_functions_stream.called
        call_kwargs = mock_llm.chat_with_functions_stream.call_args.kwargs
        system_instruction = call_kwargs.get("system_instruction", "")

        assert "MODO LIFEOS (SECRETÁRIO ÁGIL)" in system_instruction
        assert "1 a 2 frases claras e objetivas" in system_instruction
        assert "Confirmação imediata e explícita" in system_instruction
        assert call_kwargs.get("mode") == "lifeos"

    def test_auto_mode_routes_and_injects_correct_prompt(self, mock_orchestrator):
        orchestrator, mock_llm = mock_orchestrator

        # Envia comando de programação em modo auto
        plan = orchestrator.handle_request(
            "Crie um script python para ordenar uma lista com tipagem estrita",
            mode="auto",
        )

        assert mock_llm.chat_with_functions_stream.called
        call_kwargs = mock_llm.chat_with_functions_stream.call_args.kwargs
        system_instruction = call_kwargs.get("system_instruction", "")

        # Auto-routing deve ter escolhido coder
        assert call_kwargs.get("mode") == "coder"
        assert "MODO CODER PRO" in system_instruction
        assert plan.context.get("active_mode") == "coder"
        assert plan.context.get("mode_resolution", {}).get("strategy") == "auto"
