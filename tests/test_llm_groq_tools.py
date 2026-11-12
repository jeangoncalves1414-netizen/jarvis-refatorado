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


def test_lists_then_creates_in_the_same_turn(groq_script):
    completions = groq_script([[_tool_chunk("notes", '{"action":"list"}', "a")],
                               [_tool_chunk("notes", '{"action":"create"}', "b")],
                               [_text_chunk("Criado.")]])
    calls = []
    reply = _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS,
                                       on_function_call=lambda n, a: calls.append(a["action"]) or "ok")
    assert calls == ["list", "create"] and reply == "Criado."
    from app.agent.context_budget import estimate_tokens
    assert sum(estimate_tokens(c["messages"], c["tools"]) for c in completions.calls) <= 6000


def test_unoffered_tool_is_not_executed(groq_script):
    groq_script([[_tool_chunk("evil")], [_text_chunk("Não executado.")]])
    calls = []
    _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=lambda *a: calls.append(a))
    assert calls == []


def test_registry_selected_tools_survive_provider_adapter(groq_script):
    completions = groq_script([[_text_chunk("ok")]])
    selected = [{"name": name, "parameters": {"type": "object", "properties": {}}} for name in ("web_search", "video_analyst", "media_tool", "persona_tool")]
    _service()._chat_groq_stream("sys", [{"role": "user", "content": "reproduza um vídeo motivacional"}], tools=selected, on_function_call=lambda *_: "ok")
    assert {item['function']['name'] for item in completions.calls[0]['tools']} == {item['name'] for item in selected}


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

    assert reply == "A ferramenta notes falhou; nada foi confirmado."
    assert not reply.startswith("Resultados das ferramentas:")
    assert "Pronto" not in reply
    assert chunks == [reply]


def test_final_quota_error_never_reexecutes_tools(groq_script, monkeypatch):
    from app.services import llm
    monkeypatch.setattr(llm, '_key_rotator', llm.KeyRotator())
    completions = groq_script([[_tool_chunk("notes")], RuntimeError("429 tokens per day. Please try again in 10m3s.")])
    calls = []
    service = LLMService(SimpleNamespace(groq_api_keys=['chave-falsa']))
    reply = service._chat_groq_stream('sys', _MESSAGES, tools=_TOOLS, on_function_call=lambda *args: calls.append(args) or 'Nota registrada.')
    assert len(calls) == 1 and len(completions.calls) == 2
    assert 'Nota registrada.' in reply and 'sem repetir' in reply and '604 segundos' in reply


def test_synthesis_error_after_tool_returns_results_without_rerun(groq_script) -> None:
    completions = groq_script([[_tool_chunk("notes")], RuntimeError("APIError 500")])
    calls = []
    chunks: list[str] = []
    reply = _service()._chat_groq_stream("sys", _MESSAGES, tools=_TOOLS, on_function_call=lambda *args: calls.append(args) or "Nota registrada.", on_chunk=chunks.append)
    assert "Nota registrada." in reply and "não consegui redigir" in reply
    assert len(calls) == 1 and len(completions.calls) == 2
    assert chunks == [reply]


def test_synthesis_quota_with_free_second_key_never_reruns_tools(groq_script, monkeypatch):
    from app.services import llm
    monkeypatch.setattr(llm, '_key_rotator', llm.KeyRotator())
    monkeypatch.setattr(LLMService, "_api_key_for", lambda self, provider: llm._key_rotator.get_key(provider, self.settings))
    completions = groq_script([[_tool_chunk("notes")], RuntimeError("429 rate limit reached. Please try again in 5s.")])
    calls = []
    service = LLMService(SimpleNamespace(groq_api_keys=['chave-a', 'chave-b']))
    reply = service._chat_groq_stream('sys', _MESSAGES, tools=_TOOLS, on_function_call=lambda *args: calls.append(args) or 'Nota registrada.')
    assert len(calls) == 1 and len(completions.calls) == 2
    assert 'Nota registrada.' in reply and 'sem repetir' in reply


def test_oversize_retry_is_bounded_and_preserves_rules_and_latest_request(groq_script):
    completions = groq_script([RuntimeError('413 too large'), RuntimeError('413 too large')])
    messages = [{'role': 'user', 'content': 'antigo'}] * 6 + [{'role': 'user', 'content': 'x' * 4000}]
    with pytest.raises(RuntimeError, match='413'):
        _service()._chat_groq_stream('regras' * 500, messages, tools=_TOOLS)
    assert len(completions.calls) == 2
    assert completions.calls[1]['messages'][0]['content'] == 'regras' * 500
    assert completions.calls[1]['messages'][-1]['content'] == 'x' * 4000
    assert completions.calls[1]['tools']
