"""Rodada de ferramentas do Groq com cliente falso: falha nunca vira sucesso (MG4)."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.config import load_settings
from app.core.runs import RunCancelled
from app.services.llm import LLMService


def _text_chunk(text: str):
    delta = SimpleNamespace(content=text, reasoning=None, reasoning_content=None, tool_calls=None)
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


def _tool_chunk(name: str, arguments: str = "{}", call_id: str = "call_1"):
    fn = SimpleNamespace(name=name, arguments=arguments)
    call = SimpleNamespace(index=0, id=call_id, function=fn)
    delta = SimpleNamespace(content=None, reasoning=None, reasoning_content=None, tool_calls=[call])
    return SimpleNamespace(choices=[SimpleNamespace(delta=delta)])


class _FakeCompletions:
    def __init__(self, script: list) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append({"messages": [dict(m) for m in kwargs["messages"]], "tools": kwargs.get("tools")})
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return iter(step)


@pytest.fixture
def groq_script(monkeypatch: pytest.MonkeyPatch):
    holder: dict = {}

    def install(script: list) -> _FakeCompletions:
        completions = _FakeCompletions(script)

        class FakeGroq:
            def __init__(self, *args, **kwargs) -> None:
                self.chat = SimpleNamespace(completions=completions)

        monkeypatch.setitem(sys.modules, "groq", SimpleNamespace(Groq=FakeGroq))
        holder["completions"] = completions
        return completions

    monkeypatch.setattr(LLMService, "_api_key_for", lambda self, provider: "chave-falsa")
    monkeypatch.setattr(LLMService, "_effective_chat_model", lambda self, provider=None: "modelo-falso")
    return install


def _service() -> LLMService:
    return LLMService(settings=load_settings())


_TOOLS = [{"name": "notes", "description": "anota", "parameters": {"type": "object", "properties": {}}}]
_MESSAGES = [{"role": "user", "content": "anote comprar pão"}]


def test_tool_exception_is_reported_as_failure(groq_script) -> None:
    completions = groq_script([[_tool_chunk("notes")], [_text_chunk("Não consegui anotar.")]])

    def boom(name, args):
        raise RuntimeError("disco cheio")

    chunks: list[str] = []
    reply = _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=boom, on_chunk=chunks.append)

    assert reply == "Não consegui anotar."
    final_prompt = completions.calls[1]["messages"][-1]["content"]
    assert "A ferramenta notes falhou; nada foi confirmado." in final_prompt
    assert "sucesso" not in final_prompt.lower()


def test_empty_tool_result_is_not_reported_as_success(groq_script) -> None:
    completions = groq_script([[_tool_chunk("notes")], [_text_chunk("ok")]])

    _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=lambda n, a: "", on_chunk=None)

    final_prompt = completions.calls[1]["messages"][-1]["content"]
    assert "nada foi confirmado" in final_prompt
    assert "sucesso" not in final_prompt.lower()


def test_run_cancelled_from_tool_is_not_swallowed(groq_script) -> None:
    groq_script([[_tool_chunk("notes")], [_text_chunk("nunca chega")]])

    def cancelled(name, args):
        raise RunCancelled("cancelado")

    with pytest.raises(RunCancelled):
        _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=cancelled, on_chunk=None)


def test_fallback_summary_has_no_pronto_when_tool_failed(groq_script) -> None:
    groq_script([
        [_tool_chunk("notes")],
        RuntimeError("Tool choice is none, but model called a tool"),
        RuntimeError("falha de rede"),
    ])

    def boom(name, args):
        raise RuntimeError("disco cheio")

    chunks: list[str] = []
    reply = _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=boom, on_chunk=chunks.append)

    assert reply.startswith("Resultados das ferramentas:")
    assert "A ferramenta notes falhou; nada foi confirmado." in reply
    assert "Pronto" not in reply
    assert chunks == [reply]
