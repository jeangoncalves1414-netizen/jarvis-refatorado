"""Track conversation turns without persisting prompts or model deliberation."""
from functools import wraps
from inspect import signature

from app.core.runs import RunCancelled, current_run, check_run_cancelled


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
        run = action_store.create_run(session_id=bound.arguments.get("session_id"), mode=bound.arguments.get("mode", "general"))
        token = current_run.set((action_store, run.id))
        failed = True

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
                action_store.finish_run(run.id, failed=failed)
            finally:
                current_run.reset(token)

    return tracked
