"""Track conversation turns without persisting prompts or model deliberation."""
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import wraps
from inspect import signature
from typing import Any

from app.core.runs import REQUEST_ORIGINS, RunCancelled, current_origin, current_run, check_run_cancelled, run_origin


def track_run(method):
    parameters = signature(method)

    @wraps(method)
    def tracked(*args, **kwargs):
        from app.agent.orchestrator import AgentPlan
        from app.storage.action_store import action_store

        bound = parameters.bind(*args, **kwargs)
        # Nested entry points belong to the caller's request, including failures.
        if current_run.get() is not None:
            check_run_cancelled()
            result = method(*bound.args, **bound.kwargs)
            check_run_cancelled()
            return result
        requested = bound.arguments.get("origin")
        origin = requested if requested in REQUEST_ORIGINS else current_origin.get()
        run = action_store.create_run(session_id=bound.arguments.get("session_id"), mode=bound.arguments.get("mode", "general"), origin=origin)
        token = current_run.set((action_store, run.id))
        failed = True
        import time
        requested_at = time.time() * 1000
        result = None

        def guarded(callback):
            def emit(*values):
                action_store.check_cancelled(run.id)
                if callback:
                    return callback(*values)
            return emit

        # Providers that cannot interrupt a request remain cancel_requested until return.
        for name in ("on_chunk", "on_reasoning", "on_search"):
            if bound.arguments.get(name) is not None:
                bound.arguments[name] = guarded(bound.arguments[name])
        try:
            try:
                progress = bound.arguments.get("on_progress")
                if origin == "voice" and progress:
                    progress({"phase": "started", "run_id": run.id})
                result = method(*bound.args, **bound.kwargs)
                action_store.check_cancelled(run.id)
                failed = result.intent == "error" or (result.context.get("success") is False and not result.context.get("pending_action_id"))
            except RunCancelled:
                failed = False
                result = AgentPlan(intent="cancelled", summary="Pedido cancelado. Etapas já executadas não foram desfeitas.", actions=[])
            result.context = {**result.context, "run_id": run.id}
            return result
        finally:
            try:
                session_id = bound.arguments.get("session_id")
                if session_id and "text" in bound.arguments:
                    from app.storage.session_store import save_turn
                    save_turn(session_id, run.id, bound.arguments["text"],
                              result.summary if result is not None else "Não foi possível concluir o pedido. Tente novamente.",
                              timestamp=requested_at, failed=failed)
            finally:
                try:
                    action_store.finish_run(run.id, failed=failed)
                finally:
                    current_run.reset(token)

    return tracked


def record_run_step(summary: str, *, kind: str = "step") -> None:
    """Grava uma etapa interna (sem ferramenta) no pedido em andamento, se houver (C6)."""
    context = current_run.get()
    if context is None:
        return
    try:
        context[0].add_run_event(context[1], kind, summary)
    except Exception:
        # O histórico nunca derruba o pedido.
        pass


class BackgroundRun:
    """Resultado de um trabalho em segundo plano registrado como pedido."""

    def __init__(self) -> None:
        self.failed = False

    def step(self, summary: str) -> None:
        record_run_step(summary)

    def fail(self, summary: str) -> None:
        self.failed = True
        record_run_step(summary, kind="failure")


@contextmanager
def background_run(*, mode: str, source: str, origin: str | None = None, session_id: str | None = None) -> Iterator[BackgroundRun]:
    """Abre um pedido para trabalho sem ferramenta fora de um turno (memória, Swarm direto) (C6).

    Dentro de um pedido já aberto, as etapas vão para ele. Exceção dentro do bloco marca o pedido
    como falho e é propagada.
    """
    import app.storage.action_store as store_module

    handle = BackgroundRun()
    if current_run.get() is not None:
        yield handle
        return
    store = store_module.action_store
    run = store.create_run(session_id=session_id, mode=mode, source=source, origin=run_origin(origin or current_origin.get()))
    token = current_run.set((store, run.id))
    try:
        try:
            yield handle
        except BaseException:
            handle.failed = True
            raise
    finally:
        try:
            store.finish_run(run.id, failed=handle.failed)
        finally:
            current_run.reset(token)


def in_background(target: Callable[..., Any], *, label: str, run_id: str | None = None, mode: str = "memory") -> Callable[..., None]:
    """Embrulha ``target`` para rodar numa thread e deixar rastro na Central (C6).

    O trabalho vira um evento do pedido que o originou (o atual, ou ``run_id``), mesmo que o
    pedido já tenha terminado. Sem pedido de origem, abre um pedido próprio em segundo plano.
    Contextos não passam para outra thread, por isso pedido e origem são lidos agora.
    """
    import app.storage.action_store as store_module

    context = current_run.get()
    store = context[0] if context else store_module.action_store
    parent = run_id or (context[1] if context else None)
    origin = current_origin.get()

    def runner(*args: Any, **kwargs: Any) -> None:
        if parent is None:
            with background_run(mode=mode, source="background", origin=origin) as job:
                try:
                    saved = target(*args, **kwargs)
                except Exception as exc:
                    job.fail(f"{label}: falhou ({type(exc).__name__}).")
                    return
                if saved is False:
                    job.fail(f"{label}: não foi gravado (memória indisponível).")
                else:
                    job.step(f"{label}: concluído.")
            return
        try:
            if target(*args, **kwargs) is False:
                kind, summary = "background_failed", f"{label}: não foi gravado (memória indisponível)."
            else:
                kind, summary = "background", f"{label}: concluído em segundo plano."
        except Exception as exc:
            kind, summary = "background_failed", f"{label}: falhou em segundo plano ({type(exc).__name__})."
        try:
            store.add_run_event(parent, kind, summary)
        except Exception:
            pass

    return runner
