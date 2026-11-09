"""POST /api/notes/live: salva a anotação ao vivo do popup no cofre (lote 6, Fase 4).

Só pedidos locais (como a captura de microfone). A gravação passa pelo Action Kernel
(``vault_save_note`` com origem ``window``): aparece na Central e falha real vira erro.
O título no cofre é estável por rascunho, então salvar de novo sobrescreve o mesmo arquivo.
"""
from __future__ import annotations

import json
import re
from typing import Any

NOTES_FOLDER = "05-Notas"
NOTE_FORMATS = ("text", "bullets", "checklist")
MAX_TITLE = 80
MAX_CONTENT = 20_000
_DRAFT_ID = re.compile(r"^[a-z0-9]{8,32}$")
_LOOPBACK = {"127.0.0.1", "::1", "::ffff:127.0.0.1"}


def _is_local(handler: Any) -> bool:
    client = handler.client_address[0] if getattr(handler, "client_address", None) else ""
    return client in _LOOPBACK


def stable_title(title: str, draft_id: str) -> str:
    """Título gravado no cofre: o da usuária mais um sufixo curto do rascunho (evita sobrescrever outra nota)."""
    return f"{title} ({draft_id[:6]})"


def _validate(payload: Any) -> tuple[str, str, str, str]:
    if not isinstance(payload, dict):
        raise ValueError("JSON inválido.")
    draft_id = payload.get("draft_id")
    if not isinstance(draft_id, str) or not _DRAFT_ID.match(draft_id):
        raise ValueError("Rascunho inválido.")
    title = payload.get("title")
    if not isinstance(title, str) or not title.strip() or len(title.strip()) > MAX_TITLE:
        raise ValueError(f"O título da anotação deve ter de 1 a {MAX_TITLE} caracteres.")
    note_format = payload.get("format", "bullets")
    if note_format not in NOTE_FORMATS:
        raise ValueError("Formato inválido: use text, bullets ou checklist.")
    content = payload.get("content")
    if not isinstance(content, str):
        raise ValueError("O conteúdo da anotação deve ser texto.")
    if len(content) > MAX_CONTENT:
        raise ValueError("A anotação deve ter no máximo 20.000 caracteres.")
    if not content.strip():
        raise ValueError("A anotação está vazia.")
    return draft_id, title.strip(), note_format, content


def handle_notes_live_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/notes/live":
        return None
    if not _is_local(handler):
        return 403, {"ok": False, "error": "Salvar anotação ao vivo só aceita pedidos locais."}
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        draft_id, title, _note_format, content = _validate(payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}

    from app.agent.action_gateway import run_action

    saved_title = stable_title(title, draft_id)
    outcome = run_action(
        "vault_save_note",
        {"title": saved_title, "content": content, "folder": NOTES_FOLDER},
        source="popup:live_notes",
        user_text="Salvar anotação",
        origin="window",
    )
    action = outcome.action.public_dict() if outcome.action else None
    if outcome.succeeded:
        data = outcome.result.data if outcome.result else {}
        return 200, {"ok": True, "path": data.get("path"), "title": saved_title, "action": action}
    if outcome.pending:
        return 202, {"ok": False, "pending": True, "error": "A gravação da anotação aguarda aprovação na Central.", "action": action}
    message = outcome.result.message if outcome.result and outcome.result.message else "Não foi possível salvar a anotação no cofre."
    return 500, {"ok": False, "error": message, "action": action}
