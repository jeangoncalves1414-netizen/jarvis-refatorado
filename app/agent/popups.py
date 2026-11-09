"""Popups do painel (lote 6, Fase 3): modelos prontos que o agente escolhe e o backend monta.

O agente só escolhe um modelo deste registro e passa seletores validados; números e listas
vêm dos serviços, nunca do texto do modelo. O espelho no frontend (ids e validação de ``data``)
está em ``frontend/src/popups/registry.ts``.

Um popup nasce de dois jeitos:
- pela ferramenta ``show_popup`` (pedido explícito);
- automaticamente, depois de uma ferramenta de dados que deu certo (``AUTO_POPUPS``, preenchido
  na Fase 4), sem chamada extra ao modelo.

``emit`` publica o evento ``ui_popup`` no barramento (WebSocket do chat), acumula o popup no
coletor do turno (vai em ``plan.context["ui_popups"]``) e avisa o SSE da ligação. Popup nunca
derruba a ação: toda falha aqui é engolida pelo gancho do Action Kernel.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from app.core import ui_events
from app.core.runs import REQUEST_ORIGINS, current_origin, current_run

POPUP_VERSION = 1
POPUP_ORIGINS = ("chat", "voice", "command")

Validator = Callable[[Any], Any]
Builder = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]


def _text(limit: int) -> Validator:
    def check(value: Any) -> str:
        if not isinstance(value, str):
            raise ValueError("deve ser texto")
        cleaned = value.strip()
        if len(cleaned) > limit:
            raise ValueError(f"deve ter no máximo {limit} caracteres")
        return cleaned
    return check


def _choice(*options: str) -> Validator:
    def check(value: Any) -> str:
        if not isinstance(value, str) or value.strip().lower() not in options:
            raise ValueError("deve ser um de: " + ", ".join(options))
        return value.strip().lower()
    return check


def _text_list(max_items: int, limit: int) -> Validator:
    def check(value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            raise ValueError("deve ser uma lista de textos")
        if len(value) > max_items:
            raise ValueError(f"deve ter no máximo {max_items} itens")
        items: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("deve ser uma lista de textos")
            cleaned = item.strip()
            if len(cleaned) > limit:
                raise ValueError(f"deve ter itens de no máximo {limit} caracteres")
            if cleaned:
                items.append(cleaned)
        return items
    return check


@dataclass(frozen=True)
class PopupSpec:
    title: str
    params: dict[str, Validator]
    builder: Builder
    # Chave estável: um popup visível com a mesma chave é atualizado em vez de empilhar outro.
    key: Callable[[dict[str, Any]], str]
    required: frozenset[str] = frozenset()
    # Parâmetros que chegam como lista na URL dos comandos (?lines=a&lines=b).
    list_params: frozenset[str] = frozenset()
    description: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _info_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    # Só texto: o modelo informa título e linhas; nenhum número calculado entra aqui.
    return {"title": params["title"], "lines": list(params.get("lines", [])), "tone": params.get("tone", "info")}


POPUP_TEMPLATES: dict[str, PopupSpec] = {
    "info": PopupSpec(
        title="Aviso",
        params={"title": _text(60), "lines": _text_list(6, 120), "tone": _choice("info", "ok", "warn")},
        builder=_info_builder,
        key=lambda _params: f"info:{uuid.uuid4().hex[:12]}",
        required=frozenset({"title"}),
        list_params=frozenset({"lines"}),
        description="aviso curto com título, até 6 linhas e tom info/ok/warn",
    ),
}

# Popups automáticos: (ferramenta, operação) → função (args, result) que devolve
# [(template, params, animate)] ou []. Preenchido na Fase 4 (hábitos, agenda, água).
AutoPopup = Callable[[dict[str, Any], Any], list[tuple[str, dict[str, Any], dict[str, Any]]]]
AUTO_POPUPS: dict[tuple[str, str], AutoPopup] = {}


def validate_popup_request(template: Any, params: Any) -> tuple[str, dict[str, Any]]:
    """Valida modelo e parâmetros. Levanta ValueError (pt-BR) se algo não estiver no registro."""
    if not isinstance(template, str) or template.strip() not in POPUP_TEMPLATES:
        raise ValueError(f"Popup desconhecido. Modelos disponíveis: {', '.join(sorted(POPUP_TEMPLATES))}.")
    tid = template.strip()
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ValueError("Os parâmetros do popup devem ser um objeto.")
    spec = POPUP_TEMPLATES[tid]
    clean: dict[str, Any] = {}
    for name, value in params.items():
        check = spec.params.get(name)
        if check is None:
            raise ValueError(f"Parâmetro '{name}' não existe no popup '{tid}'.")
        try:
            clean[name] = check(value)
        except ValueError as exc:
            raise ValueError(f"Parâmetro '{name}' {exc}.") from None
    for name in sorted(spec.required):
        if not clean.get(name):
            raise ValueError(f"Parâmetro '{name}' é obrigatório no popup '{tid}'.")
    return tid, clean


def build_popup(
    template: str,
    params: dict[str, Any] | None,
    *,
    origin: str,
    run_id: str | None = None,
    session_id: str | None = None,
    key: str | None = None,
    animate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Monta o objeto ``popup`` do envelope (seção c do plano) com dados lidos no backend."""
    from app.storage.runtime_settings import get_popup_settings

    tid, clean = validate_popup_request(template, params)
    spec = POPUP_TEMPLATES[tid]
    context = {"origin": origin, "run_id": run_id, "session_id": session_id}
    data = spec.builder(clean, context)
    settings = get_popup_settings()
    title = data.get("title") if tid == "info" else spec.title
    return {
        "id": f"pop_{uuid.uuid4().hex}",
        "key": key or spec.key(clean),
        "template": tid,
        "version": POPUP_VERSION,
        "title": str(title or spec.title)[:80],
        "origin": origin if origin in POPUP_ORIGINS else "chat",
        "created_at": time.time(),
        "ttl_ms": int(settings["ttl_seconds"]) * 1000,
        "pinned": False,
        "data": data,
        "animate": dict(animate or {}),
    }


def emit(popup: dict[str, Any], *, session_id: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    """Publica no barramento, acumula no coletor do turno e avisa o SSE. Nunca levanta."""
    collector = ui_events.current_popups.get()
    if collector is not None:
        collector.append(popup)
    ui_events.publish({"type": "ui_popup", "session_id": session_id, "run_id": run_id, "popup": popup})
    listener = ui_events.current_popup_listener.get()
    if listener is not None:
        try:
            listener(popup)
        except Exception:
            pass
    return popup


def popups_for_result(tool_name: str, args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Popups automáticos para o resultado de uma ferramenta de dados (zero chamada ao modelo)."""
    operation = str((args or {}).get("action") or "")
    maker = AUTO_POPUPS.get((tool_name, operation))
    return maker(args or {}, result) if maker else []


def _turn_origin() -> str | None:
    """Origem do turno de conversa em andamento; None fora de um turno (janela, segundo plano)."""
    if ui_events.current_popups.get() is None:
        return None
    origin = current_origin.get()
    return origin if origin in REQUEST_ORIGINS else None


def after_tool_success(tool_name: str, args: dict[str, Any], result: Any) -> list[dict[str, Any]]:
    """Gancho do Action Kernel depois de uma ação ``succeeded``: emite os popups do resultado."""
    origin = _turn_origin()
    if origin is None:
        return []
    from app.storage.runtime_settings import get_popup_settings

    settings = get_popup_settings()
    if not settings["enabled"]:
        return []
    requests: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    if tool_name == "show_popup":
        data = getattr(result, "data", None) or {}
        request = data.get("ui_popup") if isinstance(data, dict) else None
        if isinstance(request, dict):
            requests.append((request.get("template"), request.get("params") or {}, {}))
    elif settings["auto"]:
        requests.extend(popups_for_result(tool_name, args, result))
    if not requests:
        return []
    run = current_run.get()
    run_id = run[1] if run else None
    session_id = ui_events.current_popup_session.get()
    emitted: list[dict[str, Any]] = []
    for template, params, animate in requests:
        try:
            popup = build_popup(template, params, origin=origin, run_id=run_id, session_id=session_id, animate=animate)
        except Exception:
            # Popup inválido ou serviço fora do ar: a ação continua valendo.
            continue
        emitted.append(emit(popup, session_id=session_id, run_id=run_id))
    return emitted
