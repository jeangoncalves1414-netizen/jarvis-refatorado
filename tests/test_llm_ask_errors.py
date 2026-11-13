"""Erro do provedor no ``ask`` nunca vira plano do loop agêntico (A4)."""
from __future__ import annotations

from types import SimpleNamespace

from app.agent.react_loop import ReActLoopEngine
from app.agent.tools.base import ToolResult
from app.core.actions import ToolMetadata
from app.services.llm import LLMService, ProviderErrorText


class _Registry:
    def __init__(self):
        self.tools = {"timer": SimpleNamespace(description="Ferramenta timer", parameters={"type": "object", "properties": {}})}
        self.calls = []

    def get_tool_metadata(self, name):
        return ToolMetadata((name,), "observe")

    def execute_tool(self, name, args, **_kwargs):
        self.calls.append((name, args))
        return ToolResult(True, "ok")


def _service(monkeypatch, error: Exception) -> LLMService:
    def boom(self, *args, **kwargs):
        raise error

    monkeypatch.setattr(LLMService, "get_active_provider", lambda self, override=None: "groq")
    monkeypatch.setattr(LLMService, "_api_key_for", lambda self, provider: "chave-falsa")
    monkeypatch.setattr(LLMService, "generate", boom)
    return LLMService(settings=SimpleNamespace())


def test_ask_returns_provider_error_text_with_safe_reason(monkeypatch):
    reply = _service(monkeypatch, RuntimeError("401 invalid api key sk-segredo-123")).ask("oi")
    assert isinstance(reply, ProviderErrorText) and isinstance(reply, str)
    assert reply.reason == "Chave recusada pelo provedor."
    assert "sk-" not in reply.reason


def test_ask_without_key_returns_provider_error_text(monkeypatch):
    monkeypatch.setattr(LLMService, "get_active_provider", lambda self, override=None: "groq")
    monkeypatch.setattr(LLMService, "_api_key_for", lambda self, provider: "")
    monkeypatch.setattr(LLMService, "unavailable_reason", lambda self, provider: "")
    reply = LLMService(settings=SimpleNamespace()).ask("oi")
    assert isinstance(reply, ProviderErrorText)
    assert reply.reason == str(reply) and "GROQ_API_KEY" in reply


def test_react_loop_stops_on_provider_error_without_running_tools():
    registry = _Registry()
    error = ProviderErrorText("Erro ao acessar a API do Groq: 500 sk-segredo", reason="Erro do provedor (RuntimeError).")
    engine = ReActLoopEngine(SimpleNamespace(ask=lambda prompt: error), registry, allowed_tools=frozenset({"timer"}))
    trajectory = engine.run_loop("ligue um timer de 5 minutos", progress=lambda event: None)
    assert trajectory.stopped_reason == "invalid_plan" and trajectory.success is False
    assert registry.calls == [] and trajectory.action_steps == []
    assert "Erro ao acessar a API" not in trajectory.final_output and "sk-" not in trajectory.final_output
    assert trajectory.final_output.startswith("O planejamento falhou: Erro do provedor (RuntimeError).")
    assert "Nada mais foi executado" in trajectory.final_output

def test_gemini_stream_tolerates_empty_candidates_and_parts(monkeypatch):
    from google import genai
    chunks = [SimpleNamespace(text=None, candidates=None), SimpleNamespace(text=None, candidates=[SimpleNamespace(content=SimpleNamespace(parts=None))]), SimpleNamespace(text='Resposta real', candidates=[])]
    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=lambda **kwargs: iter(chunks)))
    monkeypatch.setattr(genai, 'Client', lambda **kwargs: client)
    monkeypatch.setattr(LLMService, '_api_key_for', lambda self, provider: 'fixture-key')
    monkeypatch.setattr(LLMService, '_effective_chat_model', lambda *args: 'fixture-model')
    service = LLMService(settings=SimpleNamespace())
    assert service._chat_gemini_stream('', [{'role':'user','content':'oi'}]) == 'Resposta real'
