"""Rota de modelo por pedido, isolada entre threads e chamadas aninhadas."""
from contextvars import ContextVar

current_model_mode: ContextVar[str] = ContextVar("model_mode", default="chat")


def route_key(mode: str, origin: str = "chat") -> str:
    if origin == "voice" and mode in {"auto", "general", "chat"}:
        return "voice"
    return "chat" if mode in {"auto", "general", "chat"} else mode
