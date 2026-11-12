"""Memórias com fonte pelo Action Kernel (fase contexto 2).

Painel e gatilhos salvam, editam e removem por ``run_action("memory_tool", ...)``: cada mudança
vira uma ação na Central (recibo) com risco ``low``; o ``execute=`` do gateway chama o store direto.
O modelo usa a ferramenta ``memory`` (app/agent/tools/memory_tool.py), que já roda dentro da
ação do turno e por isso grava com ``save_fact`` (sem recibo ``memory_tool`` aninhado).
"""
from __future__ import annotations

from typing import Any

from app.agent.tools.base import ToolResult
from app.core.runs import REQUEST_ORIGINS, current_origin, current_run
from app.services import memory_slots
from app.storage import memory_facts

_SOURCE_ORIGIN = {"voice": "voz", "window": "painel", "chat": "chat"}
_LABELS = {"save": "Salvar memória", "update": "Editar memória", "delete": "Remover memória"}


def _run_origin(origin: str | None) -> str:
    if origin in (*REQUEST_ORIGINS, "window"):
        return origin  # type: ignore[return-value]
    return current_origin.get() if current_origin.get() in REQUEST_ORIGINS else "chat"


def _run(operation: str, arguments: dict[str, Any], origin: str | None, call) -> dict[str, Any]:
    from app.agent.action_gateway import run_action

    resolved = _run_origin(origin)
    captured: dict[str, Any] = {}

    def execute(_args: dict[str, Any]) -> ToolResult:
        try:
            fact = call()
        except ValueError as exc:
            captured["error"] = str(exc)
            return ToolResult(False, str(exc))
        captured["fact"] = fact
        return ToolResult(True, f"{_LABELS[operation]}: {fact.get('text', '')[:80]}", data={"fact": fact})

    detail = arguments.get("text") or arguments.get("id") or ""
    outcome = run_action(
        "memory_tool", {"operation": operation, **arguments}, source="memoria",
        user_text=f"{_LABELS[operation]}: {str(detail)[:80]}", origin=resolved, execute=execute,
    )
    action = outcome.action.public_dict() if outcome.action is not None else None
    if outcome.succeeded and "fact" in captured:
        return {"ok": True, "fact": captured["fact"], "action": action}
    return {"ok": False, "error": captured.get("error") or "Não foi possível gravar a memória.", "action": action}


def _source(kind: str, session_id: str | None, origin: str | None) -> dict[str, Any]:
    turn = current_run.get()
    return {
        "session_id": session_id or "", "run_id": turn[1] if turn else "",
        "origin": _SOURCE_ORIGIN.get(_run_origin(origin), "chat"), "kind": kind,
    }


def save_fact(text: str, *, kind: str, session_id: str | None = "", origin: str | None = None,
              pinned: bool | None = None, importance: float | None = None) -> dict[str, Any]:
    """Grava o fato com fonte sem abrir outra ação (quem chama já está dentro de uma)."""
    clean = " ".join(str(text or "").split())
    return memory_facts.save(clean, source=_source(kind, session_id, origin), pinned=pinned, importance=importance)


def save_via_kernel(text: str, *, kind: str, session_id: str | None = "", origin: str | None = None) -> dict[str, Any]:
    resolved = _run_origin(origin)
    clean = " ".join(str(text or "").split())
    return _run("save", {"text": clean}, resolved,
                lambda: save_fact(clean, kind=kind, session_id=session_id, origin=resolved))


def update_via_kernel(fact_id: str, text: str, *, origin: str | None = None) -> dict[str, Any]:
    return _run("update", {"id": fact_id, "text": text}, origin, lambda: memory_facts.update(fact_id, text))


def delete_via_kernel(fact_id: str, *, origin: str | None = None) -> dict[str, Any]:
    return _run("delete", {"id": fact_id}, origin, lambda: memory_facts.delete(fact_id))


def save_trigger_memory(text: str, *, session_id: str | None = None) -> dict[str, Any] | None:
    """Gatilho do lote 7: grava o fato com fonte só quando o parser acha um slot. Nunca levanta."""
    try:
        if memory_slots.parse(text) is None:
            return None
        return save_via_kernel(str(text).strip()[: memory_facts.MAX_TEXT], kind="gatilho", session_id=session_id)
    except Exception as exc:
        from app.agent.run_tracking import record_run_step

        record_run_step(f"Memória do gatilho não gravada ({type(exc).__name__}).", kind="failure")
        return None
