"""POST /api/vault/*: gravações do cofre feitas pela janela (MG10).

As três sub-rotas (``notes``, ``daily/log``, ``profile/fact``) passam pelo Action Kernel com
origem ``window`` (``vault_save_note``, ``vault_daily_log`` e ``vault_update_profile``), então
aparecem na Central. A pasta da nota vem da mesma lista da ferramenta do agente
(``NOTE_FOLDERS``) e ainda é conferida com ``resolve()`` + ``relative_to(VAULT_DIR)``: ``..`` e
caminho absoluto são recusados.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agent.tools.memory_vault_tool import MAX_CONTENT, MAX_ENTRY, MAX_TITLE, NOTE_FOLDERS

DEFAULT_FOLDER = "04-Projects"
MAX_FACT = 300


def resolve_note_folder(folder: Any) -> str:
    """Pasta de nota aceita; qualquer outra coisa levanta ``ValueError`` com mensagem em português."""
    from app.services import memory_vault as vault_module

    if folder is None or (isinstance(folder, str) and not folder.strip()):
        folder = DEFAULT_FOLDER
    if not isinstance(folder, str):
        raise ValueError("A pasta da nota deve ser texto.")
    name = folder.strip()
    allowed = "Use uma de: " + ", ".join(NOTE_FOLDERS) + "."
    if ".." in name or Path(name).is_absolute() or name.startswith(("/", "\\")) or ":" in name:
        raise ValueError(f"Pasta inválida: caminhos com '..' ou absolutos não são aceitos. {allowed}")
    if name not in NOTE_FOLDERS:
        raise ValueError(f"Pasta inválida. {allowed}")
    vault = Path(vault_module.VAULT_DIR).resolve()
    try:
        (vault / name).resolve().relative_to(vault)
    except ValueError:
        raise ValueError(f"Pasta inválida: fora do cofre. {allowed}") from None
    return name


def _text(payload: dict[str, Any], key: str, default: str = "") -> str:
    value = payload.get(key, default)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"O campo '{key}' deve ser texto.")
    return value


def _run(tool: str, arguments: dict[str, Any], user_text: str, failure: str) -> tuple[int, dict[str, Any]]:
    from app.agent.action_gateway import run_action

    outcome = run_action(tool, arguments, source="api:vault", user_text=user_text, origin="window")
    action = outcome.action.public_dict() if outcome.action else None
    if outcome.succeeded:
        data = outcome.result.data if outcome.result else {}
        return 200, {"ok": True, "path": data.get("path"), "action": action}
    if outcome.pending:
        return 202, {"ok": False, "pending": True, "error": "A gravação no cofre aguarda aprovação na Central.", "action": action}
    message = outcome.result.message if outcome.result and outcome.result.message else failure
    return 500, {"ok": False, "error": message, "action": action}


def handle_vault_post(path: str, body: bytes) -> tuple[int, dict[str, Any]] | None:
    if path != "/api/vault" and not path.startswith("/api/vault/"):
        return None
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 400, {"ok": False, "error": "JSON inválido."}
    if not isinstance(payload, dict):
        return 400, {"ok": False, "error": "JSON inválido."}
    sub = path.removeprefix("/api/vault").strip("/")
    try:
        if sub == "daily/log":
            entry = _text(payload, "entry").strip()
            if not entry:
                return 400, {"ok": False, "error": "Informe o texto da entrada do diário."}
            if len(entry) > MAX_ENTRY:
                return 400, {"ok": False, "error": f"A entrada do diário deve ter no máximo {MAX_ENTRY} caracteres."}
            arguments = {"entry": entry, "category": _text(payload, "category", "Atividade")}
            return _run("vault_daily_log", arguments, "Registrar no diário de hoje", "Não foi possível registrar no diário.")
        if sub == "profile/fact":
            fact = _text(payload, "fact").strip()
            if not fact:
                return 400, {"ok": False, "error": "Informe o fato ou preferência a registrar."}
            if len(fact) > MAX_FACT:
                return 400, {"ok": False, "error": f"O fato deve ter no máximo {MAX_FACT} caracteres."}
            return _run("vault_update_profile", {"fact": fact}, "Atualizar o perfil no cofre", "Não foi possível atualizar o perfil.")
        if sub == "notes":
            title = _text(payload, "title", "nota").strip() or "nota"
            content = _text(payload, "content")
            if len(title) > MAX_TITLE:
                return 400, {"ok": False, "error": f"O título da nota deve ter de 1 a {MAX_TITLE} caracteres."}
            if len(content) > MAX_CONTENT:
                return 400, {"ok": False, "error": f"O conteúdo da nota deve ter no máximo {MAX_CONTENT} caracteres."}
            folder = resolve_note_folder(payload.get("folder"))
            arguments = {"title": title, "content": content, "folder": folder}
            return _run("vault_save_note", arguments, "Salvar nota no cofre", "Não foi possível salvar a nota no cofre.")
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    return 400, {"ok": False, "error": f"Sub-rota '{sub}' não reconhecida."}
