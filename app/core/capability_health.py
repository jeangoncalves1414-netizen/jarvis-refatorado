"""Saúde real das capacidades: último sucesso, última falha e quem respondeu de fato (O1, O2).

Fica só em memória: zera quando o backend reinicia, e a página Integrações diz isso.
Nenhuma chamada de rede é feita aqui; "alcançável" vem do resultado da última chamada real.
"""
from __future__ import annotations

import re
import sys
import threading
import time
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable

from app.core.runs import RunCancelled, current_run

# Código de erro do provedor só entra no motivo se for um identificador simples (nunca texto livre).
_ERROR_CODE = re.compile(r"^[a-z0-9_]{1,40}$")


def _http_status(exc: BaseException) -> int | None:
    """Status HTTP lido dos atributos da exceção (SDKs Groq/OpenAI/Gemini), nunca da mensagem."""
    candidates = (getattr(exc, "status_code", None), getattr(getattr(exc, "response", None), "status_code", None), getattr(exc, "code", None))
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return None


def _error_code(exc: BaseException) -> str | None:
    """Código do provedor (``body["error"]["code"]``, ``body["code"]`` ou ``exc.code``) só se casar com a lista branca."""
    body = getattr(exc, "body", None)
    candidates: list[Any] = []
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            candidates.append(error.get("code"))
        candidates.append(body.get("code"))
    candidates.append(getattr(exc, "code", None))
    for value in candidates:
        if isinstance(value, str) and _ERROR_CODE.match(value):
            return value
    return None


def failure_reason(exc: BaseException | None) -> str:
    """Motivo curto e seguro de uma falha de provedor: nunca copia a mensagem crua (pode ter chave).

    Inclui o status HTTP e o código do provedor quando a exceção os traz como atributos.
    """
    if exc is None:
        return "Falha sem detalhe."
    status, code = _http_status(exc), _error_code(exc)
    detail = f", {code}" if code else ""
    if status is not None:
        if status == 429:
            return f"Limite de uso do provedor (429{detail})."
        if status in (401, 403):
            return "Chave recusada pelo provedor."
        if status == 413 or code == "request_too_large":
            return "Pedido grande demais para o limite do provedor (413)."
        if status == 400:
            return f"Pedido recusado pelo provedor (400{detail})."
        return f"Erro do provedor (HTTP {status}{detail})."
    text = str(exc).lower()
    if "429" in text or "resource_exhausted" in text or "rate limit" in text or "quota" in text:
        return f"Limite de uso do provedor (429{detail})."
    if "401" in text or "403" in text or "unauthorized" in text or "permission" in text or "api key" in text or "api_key" in text:
        return "Chave recusada pelo provedor."
    if "413" in text or "too large" in text or code == "request_too_large":
        return "Pedido grande demais para o limite do provedor (413)."
    if "timeout" in text or "timed out" in text or isinstance(exc, TimeoutError):
        return "O provedor não respondeu a tempo."
    if isinstance(exc, (ConnectionError, OSError)) or "connection" in text:
        return "Sem conexão com o provedor."
    if "não configurada" in text or "not configured" in text:
        return "Sem chave configurada."
    return f"Erro do provedor ({type(exc).__name__})."


class CapabilityHealth:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: dict[str, dict[str, Any]] = {}
        # Ordem dos registros: o relógio do Windows pode repetir o mesmo instante.
        self._tick = 0
        self.started_at = time.time()

    def _item(self, capability: str) -> dict[str, Any]:
        return self._items.setdefault(capability, {
            "last_success_at": None, "last_failure_at": None, "last_failure_reason": None,
            "last_failure_provider": None, "provider": None, "model": None, "latency_ms": None,
            "fallback": None, "success_seq": 0, "failure_seq": 0,
        })

    def record_success(self, capability: str, *, provider: str | None = None, model: str | None = None,
                       latency_ms: int | None = None, fallback_from: str | None = None, reason: str | None = None) -> None:
        with self._lock:
            item = self._item(capability)
            now = time.time()
            self._tick += 1
            item.update(last_success_at=now, success_seq=self._tick, provider=provider, model=model, latency_ms=latency_ms)
            if fallback_from and fallback_from != provider:
                item["fallback"] = {"from": fallback_from, "to": provider, "model": model, "reason": reason or "Falha sem detalhe.", "at": now}

    def record_failure(self, capability: str, *, provider: str | None = None, reason: str) -> None:
        with self._lock:
            item = self._item(capability)
            self._tick += 1
            item.update(last_failure_at=time.time(), failure_seq=self._tick, last_failure_reason=reason[:200], last_failure_provider=provider)

    def get(self, capability: str) -> dict[str, Any]:
        with self._lock:
            return {**self._item(capability)} if capability in self._items else {}

    def snapshot(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {key: {**value} for key, value in self._items.items()}

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


capability_health = CapabilityHealth()

# Ferramenta → capacidade da página Integrações. O resultado real de cada execução pelo
# Action Kernel alimenta "último sucesso" e "alcançável".
TOOL_CAPABILITIES: dict[str, str] = {
    "spotify": "spotify", "whatsapp": "whatsapp", "telegram_bot": "telegram", "kasa_control": "kasa",
    "home": "home_assistant",
    "mcp": "mcp", "calendar": "calendar", "image_generator": "image", "vision": "vision",
    "composio": "composio", "mobile_adb": "adb",
}


def record_tool_result(tool_name: str, ok: bool, message: str | None = None) -> None:
    capability = TOOL_CAPABILITIES.get(tool_name)
    if capability is None:
        return
    try:
        if ok:
            capability_health.record_success(capability)
        else:
            from app.core.actions import redact
            capability_health.record_failure(capability, reason=str(redact(message or "A ferramenta não confirmou a conclusão.", limit=160)))
    except Exception:
        pass


def reachable_from(record: dict[str, Any]) -> bool | None:
    """Alcançável pela última chamada real: sucesso mais recente que a falha. Sem chamada: ``None``."""
    success, failure = record.get("success_seq") or 0, record.get("failure_seq") or 0
    if not success and not failure:
        return None
    return success > failure


# Estado da chamada ao modelo em andamento nesta thread (O2).
_model_call: ContextVar[dict[str, Any] | None] = ContextVar("model_call", default=None)


def _note_in_run(summary: str, kind: str) -> None:
    context = current_run.get()
    if context is None:
        return
    try:
        context[0].add_run_event(context[1], kind, summary)
    except Exception:
        pass


def _finish(state: dict[str, Any], failed: BaseException | None) -> None:
    capability = state["capability"]
    intended = state["intended"]
    failures = state["failures"]
    try:
        if failed is None and state["answered"]:
            provider, model = state["answered"]
            latency = max(1, int((time.monotonic() - state["started"]) * 1000))
            reason = failures[0]["reason"] if failures else None
            fallback_from = intended if intended and intended != provider else None
            # Falhas antes do sucesso: "alcançável" fica com a resposta que chegou por último.
            for item in failures:
                if item["provider"] != provider:
                    capability_health.record_failure(capability, provider=item["provider"], reason=item["reason"])
            capability_health.record_success(capability, provider=provider, model=model, latency_ms=latency, fallback_from=fallback_from, reason=reason)
            if fallback_from:
                _note_in_run(f"Modelo: {provider} ({model}) respondeu no lugar de {fallback_from}. Motivo: {reason or 'falha sem detalhe'}", "fallback")
        elif failed is not None or state["last_error"]:
            # Também cobre o ponto de entrada que engole a exceção e devolve texto de erro.
            reason = failure_reason(failed) if failed is not None else state["last_error"]
            name = state["stack_top"] or intended
            capability_health.record_failure(capability, provider=name, reason=reason)
            _note_in_run(f"Modelo: {name or 'provedor'} falhou. Motivo: {reason}", "failure")
    except Exception:
        # Registro de saúde nunca derruba a chamada ao modelo.
        pass


def track_model_call(provider: str | None = None, *, capability: str = "chat") -> Callable:
    """Decora métodos do serviço de modelo para registrar quem respondeu de fato (O2).

    ``provider`` marca a chamada que fala com um provedor. Sem ``provider`` (pontos de entrada
    públicos), o decorador só agrupa as tentativas: o primeiro provedor tentado é o pretendido.
    Uma tentativa chamada enquanto outra exceção é tratada conta como troca por falha.
    Exceções são repassadas sem mudança.
    """
    def decorate(method: Callable) -> Callable:
        @wraps(method)
        def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
            state = _model_call.get()
            outer = state is None
            token = None
            if outer:
                state = {"capability": capability, "intended": None, "answered": None, "failures": [],
                         "stack": [], "last_raised": None, "stack_top": None, "last_error": None, "started": time.monotonic(),
                         # Exceção que já estava sendo tratada por quem chamou: não é falha de provedor.
                         "ambient": sys.exc_info()[1]}
                token = _model_call.set(state)
            if provider:
                if state["intended"] is None:
                    state["intended"] = provider
                handling = sys.exc_info()[1]
                if handling is not None and not outer and handling is not state["ambient"]:
                    failed = state["last_raised"] or next((name for name in reversed(state["stack"]) if name), None) or state["intended"]
                    state["failures"].append({"provider": failed, "reason": failure_reason(handling)})
                    state["last_raised"] = None
            state["stack"].append(provider)
            try:
                result = method(self, *args, **kwargs)
            except BaseException as exc:
                # Cancelamento pela usuária não é falha do provedor.
                if not isinstance(exc, (RunCancelled, KeyboardInterrupt)):
                    state["last_error"] = failure_reason(exc)
                    if provider:
                        state["last_raised"] = provider
                        state["stack_top"] = provider
                    if outer:
                        _finish(state, exc)
                raise
            finally:
                state["stack"].pop()
                if outer:
                    _model_call.reset(token)
            if provider and state["answered"] is None:
                state["answered"] = (provider, _model_name(self, provider))
            if outer:
                _finish(state, None)
            return result

        return wrapped

    return decorate


def _model_name(service: Any, provider: str) -> str | None:
    try:
        return str(service._effective_chat_model(provider))
    except Exception:
        return None
