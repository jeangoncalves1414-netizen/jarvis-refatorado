"""Request identity and cooperative cancellation, independent of agent persona."""
from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
import time
import uuid

RUN_TERMINAL = frozenset({"succeeded", "failed", "cancelled", "interrupted"})
RUN_STATUSES = RUN_TERMINAL | {"running", "awaiting_confirmation", "cancel_requested"}


class RunCancelled(Exception):
    pass


@dataclass
class RunRecord:
    session_id: str | None
    mode: str
    source: str = "conversation"
    # Quem disparou o pedido (C6): ver RUN_ORIGINS. Registros antigos sem o campo contam como chat.
    origin: str = "chat"
    policy: str = "tool_metadata_confirmation_v1"
    id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex}")
    status: str = "running"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    turn_done: bool = False
    turn_failed: bool = False
    cancel_requested: bool = False
    result_summary: str | None = None

    def public_dict(self) -> dict:
        value = asdict(self)
        value.pop("turn_done")
        value.pop("turn_failed")
        return value


# Context stays local to the request thread; approval callbacks retain run_id.
current_run: ContextVar[tuple[object, str] | None] = ContextVar("current_run", default=None)

# Origem do pedido de conversa (C10): ações registradas num turno de voz levam o prefixo "voice:".
REQUEST_ORIGINS: frozenset[str] = frozenset({"chat", "voice"})
current_origin: ContextVar[str] = ContextVar("current_origin", default="chat")

# Origens que um Run pode ter (C6). Só chat e voz chegam do cliente hoje; rotina, palma e celular
# ficam reservadas para os gatilhos futuros; janela é a rota direta do painel; "system" é trabalho
# em segundo plano sem pedido da usuária (resumo diário, por exemplo).
RUN_ORIGINS: tuple[str, ...] = ("chat", "voice", "routine", "clap", "window", "mobile", "system")


def run_origin(value: object, default: str = "chat") -> str:
    """Normaliza a origem gravada num Run; valor desconhecido vira ``default``."""
    return value if isinstance(value, str) and value in RUN_ORIGINS else default


def check_run_cancelled() -> None:
    context = current_run.get()
    if context:
        context[0].check_cancelled(context[1])
