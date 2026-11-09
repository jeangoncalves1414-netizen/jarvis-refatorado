"""Popups do painel (lote 6, Fase 3): modelos prontos que o agente escolhe e o backend monta.

O agente só escolhe um modelo deste registro e passa seletores validados; números e listas
vêm dos serviços, nunca do texto do modelo. O espelho no frontend (ids e validação de ``data``)
está em ``frontend/src/popups/registry.ts``.

Um popup nasce de dois jeitos:
- pela ferramenta ``show_popup`` (pedido explícito);
- automaticamente, depois de uma ferramenta de dados que deu certo (``AUTO_POPUPS``: hábitos,
  tarefas, agenda, água e lugares), sem chamada extra ao modelo.

``emit`` publica o evento ``ui_popup`` no barramento (WebSocket do chat), acumula o popup no
coletor do turno (vai em ``plan.context["ui_popups"]``) e avisa o SSE da ligação. Popup nunca
derruba a ação: toda falha aqui é engolida pelo gancho do Action Kernel.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
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


def _iso_date(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("deve ser uma data AAAA-MM-DD")
    try:
        return date.fromisoformat(value.strip()).isoformat()
    except ValueError:
        raise ValueError("deve ser uma data AAAA-MM-DD") from None


def _bool(value: Any) -> bool:
    # A URL dos comandos manda texto ("true"/"false"); o agente manda booleano.
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in ("true", "1", "sim"):
        return True
    if isinstance(value, str) and value.strip().lower() in ("false", "0", "nao", "não"):
        return False
    raise ValueError("deve ser verdadeiro ou falso")


@dataclass(frozen=True)
class PopupSpec:
    title: str
    params: dict[str, Validator]
    builder: Builder
    # Chave estável (parâmetros validados, dados montados): um popup visível com a mesma chave é
    # atualizado em vez de empilhar outro.
    key: Callable[[dict[str, Any], dict[str, Any]], str]
    required: frozenset[str] = frozenset()
    # Parâmetros que chegam como lista na URL dos comandos (?lines=a&lines=b).
    list_params: frozenset[str] = frozenset()
    description: str = ""
    # Popup que fica até a usuária fechar (anotação ao vivo), qualquer que seja o ttl configurado.
    sticky: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def _info_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    # Só texto: o modelo informa título e linhas; nenhum número calculado entra aqui.
    return {"title": params["title"], "lines": list(params.get("lines", [])), "tone": params.get("tone", "info")}


# ── Modelos de dados (Fase 4): tudo lido dos serviços, nunca do texto do modelo ──────────────

MAX_POPUP_ITEMS = 50


def _habit_list_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    from app.agent.tools.lifestyle_tools import WEEK_DAYS, normalize_name
    from app.services.habits import HabitService

    scope = params.get("filter", "today")
    wanted = {normalize_name(name) for name in params.get("highlight", [])}
    weekday = WEEK_DAYS[date.today().weekday()]
    items: list[dict[str, Any]] = []
    highlight_ids: list[str] = []
    for habit in HabitService.list_habits():
        days = list(habit.get("days_of_week") or WEEK_DAYS)
        highlighted = normalize_name(habit.get("name")) in wanted
        # "today" mostra os hábitos de hoje e sempre os destacados (ex.: recém-criados para outro dia).
        if scope == "today" and weekday not in days and not highlighted:
            continue
        item = {
            "id": str(habit.get("id")),
            "name": str(habit.get("name") or ""),
            "category": str(habit.get("category") or ""),
            "routine_block": str(habit.get("routine_block") or "anytime"),
            "start_time": str(habit.get("start_time") or ""),
            "days_of_week": [str(day) for day in days],
            "completed_today": bool(habit.get("completed_today")),
            "streak": int(habit.get("current_streak") or 0),
        }
        items.append(item)
        if highlighted:
            highlight_ids.append(item["id"])
    items = items[-MAX_POPUP_ITEMS:]
    return {
        "filter": scope,
        "items": items,
        "completed": sum(1 for item in items if item["completed_today"]),
        "total": len(items),
        "highlight_ids": [hid for hid in highlight_ids if any(item["id"] == hid for item in items)],
    }


def _schedule_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    from app.services.calendar import CalendarService

    day = date.fromisoformat(params.get("date") or date.today().isoformat())
    events = [
        event for event in CalendarService().get_all_events()
        if event.reminder_status != "cancelled" and event.start.date() == day
    ]
    events.sort(key=lambda event: event.start)
    return {
        "date": day.isoformat(),
        "events": [
            {
                "id": event.id,
                "title": event.title,
                "start": event.start.isoformat(timespec="minutes"),
                "reminder_at": event.reminder_at.isoformat(timespec="minutes") if event.reminder_at else None,
            }
            for event in events[:MAX_POPUP_ITEMS]
        ],
    }


def _int_or(value: Any, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    return int(value)


def _water_builder(_params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    from app.services.lifeos import LifeOSService

    summary = LifeOSService.get_daily_summary()
    water = summary.get("water") or {}
    current = max(0, _int_or(water.get("current_ml"), 0))
    target = max(0, _int_or(water.get("target_ml"), 3000))
    # previous_ml = total antes da ação (vem do resultado do serviço via animate.from_ml);
    # sem ação (comando /hidratacao), é o próprio total.
    animate = context.get("animate") or {}
    previous = max(0, _int_or(animate.get("from_ml"), current))
    return {
        "date": str(summary.get("date") or date.today().isoformat()),
        "current_ml": current,
        "previous_ml": previous,
        "target_ml": target,
        "percentage": max(0, _int_or(water.get("percentage"), 0)),
    }


def _animated_ids(context: dict[str, Any], *names: str) -> set[str]:
    animate = context.get("animate") or {}
    found: set[str] = set()
    for name in names:
        values = animate.get(name)
        if isinstance(values, list):
            found.update(str(value) for value in values if value)
    return found


def _task_list_builder(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    from app.services.tasks import TaskService

    scope = params.get("filter", "pending")
    # "pending" mostra as pendentes e sempre as que a ação acabou de mexer (ex.: recém-concluída).
    focus = _animated_ids(context, "added_ids", "toggled_ids", "updated_ids")
    items: list[dict[str, Any]] = []
    for task in TaskService.list_tasks(completed=None):
        task_id = str(task.get("id") or "")
        completed = bool(task.get("completed"))
        if not task_id or (scope == "pending" and completed and task_id not in focus):
            continue
        items.append({
            "id": task_id,
            "title": str(task.get("title") or "")[:200],
            "priority": max(1, min(4, _int_or(task.get("priority"), 4))),
            "due_date": str(task.get("due_date") or "")[:10],
            "completed": completed,
        })
    if len(items) > MAX_POPUP_ITEMS:
        kept = {item["id"] for item in items if item["id"] in focus}
        rest = [item["id"] for item in items if item["id"] not in focus][: max(0, MAX_POPUP_ITEMS - len(kept))]
        kept.update(rest)
        items = [item for item in items if item["id"] in kept]
    return {
        "filter": scope,
        "items": items,
        "pending": sum(1 for item in items if not item["completed"]),
        "total": len(items),
    }


def _places_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    from app.services import places

    query, near = places.validate_search(params.get("query", ""), params.get("near", ""))
    # O popup só mostra uma busca já feita pelo Action Kernel (ferramenta ou janela Lugares):
    # montar o popup nunca envia nada ao provedor de mapas.
    found = places.cached_search(query, near)
    if not found or not found.get("ok"):
        raise ValueError("Busque o lugar primeiro (places_search ou janela Lugares); o popup só mostra buscas já feitas.")
    return {
        "query": query,
        "near": near,
        "provider": found.get("provider") if found.get("provider") in ("osm", "google") else "osm",
        "results": [{"id": f"p{index}", **item} for index, item in enumerate(found.get("results") or [])],
        "bbox": found.get("bbox"),
        "attribution": str(found.get("attribution") or ""),
        "notice": str(found.get("notice") or ""),
    }


def _places_key(params: dict[str, Any], _data: dict[str, Any]) -> str:
    from app.services import places

    return f"places:{places.search_key(params.get('query', ''), params.get('near', ''))}"


def _live_notes_builder(params: dict[str, Any], _context: dict[str, Any]) -> dict[str, Any]:
    return {
        "draft_id": uuid.uuid4().hex[:16],
        "title": params.get("title") or "Anotação",
        "format": params.get("format", "bullets"),
        "dictate": params.get("dictate", True),
        "content": "",
    }


POPUP_TEMPLATES: dict[str, PopupSpec] = {
    "info": PopupSpec(
        title="Aviso",
        params={"title": _text(60), "lines": _text_list(6, 120), "tone": _choice("info", "ok", "warn")},
        builder=_info_builder,
        key=lambda _params, _data: f"info:{uuid.uuid4().hex[:12]}",
        required=frozenset({"title"}),
        list_params=frozenset({"lines"}),
        description="aviso curto com título, até 6 linhas e tom info/ok/warn",
    ),
    "habit_list": PopupSpec(
        title="Hábitos",
        params={"filter": _choice("today", "all"), "highlight": _text_list(20, 120)},
        builder=_habit_list_builder,
        key=lambda _params, _data: "habits",
        list_params=frozenset({"highlight"}),
        description="lista de hábitos; filter today|all, highlight com nomes a destacar",
    ),
    "schedule": PopupSpec(
        title="Agenda",
        params={"date": _iso_date},
        builder=_schedule_builder,
        key=lambda _params, data: f"schedule:{data['date']}",
        description="compromissos de um dia; date AAAA-MM-DD (padrão hoje)",
    ),
    "water": PopupSpec(
        title="Água de hoje",
        params={},
        builder=_water_builder,
        key=lambda _params, data: f"water:{data['date']}",
        description="água de hoje contra a meta; sem parâmetros",
    ),
    "live_notes": PopupSpec(
        title="Anotação ao vivo",
        params={"title": _text(80), "format": _choice("text", "bullets", "checklist"), "dictate": _bool},
        builder=_live_notes_builder,
        key=lambda _params, data: f"notes:{data['draft_id']}",
        description="anotação escrita enquanto a usuária fala; title, format text|bullets|checklist, dictate",
        sticky=True,
    ),
    # Fase 5 (extras).
    "task_list": PopupSpec(
        title="Tarefas",
        params={"filter": _choice("pending", "all")},
        builder=_task_list_builder,
        key=lambda _params, _data: "tasks",
        description="tarefas; filter pending|all (padrão pending)",
    ),
    "places": PopupSpec(
        title="Lugares",
        params={"query": _text(120), "near": _text(80)},
        builder=_places_builder,
        key=_places_key,
        required=frozenset({"query"}),
        description="resultado de uma busca de lugares já feita; query (até 120), near (até 80)",
    ),
}

# Popups automáticos: (ferramenta, operação) → função (args, result) que devolve
# [(template, params, animate)] ou []. Os ids e totais vêm de ``result.data``; as listas são
# relidas dos serviços pelo builder.
AutoPopup = Callable[[dict[str, Any], Any], list[tuple[str, dict[str, Any], dict[str, Any]]]]


def _result_data(result: Any) -> dict[str, Any]:
    data = getattr(result, "data", result)
    return data if isinstance(data, dict) else {}


def _habit_names(data: dict[str, Any]) -> list[str]:
    found: list[dict[str, Any]] = [item for item in data.get("habits") or [] if isinstance(item, dict)]
    if isinstance(data.get("habit"), dict):
        found.append(data["habit"])
    names: list[str] = []
    for item in found:
        name = str(item.get("name") or "").strip()
        if name and name not in names and len(name) <= 120:
            names.append(name)
    return names[:20]


def _auto_habits(kind: str) -> AutoPopup:
    def make(_args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        data = _result_data(result)
        ids = [str(item) for item in data.get("habit_ids") or [] if item]
        if not ids:
            return []
        params: dict[str, Any] = {"filter": "today"}
        names = _habit_names(data)
        if names:
            params["highlight"] = names
        return [("habit_list", params, {kind: ids})]
    return make


def _auto_schedule(_args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    data = _result_data(result)
    events = [item for item in data.get("events") or [] if isinstance(item, dict)]
    if not events and isinstance(data.get("event"), dict):
        events = [data["event"]]
    by_day: dict[str, list[str]] = {}
    for event in events:
        try:
            day = datetime.fromisoformat(str(event.get("start"))).date().isoformat()
        except ValueError:
            continue
        if event.get("id"):
            by_day.setdefault(day, []).append(str(event["id"]))
    # Um popup por dia (no máximo 3), cada um com os compromissos novos daquele dia.
    return [("schedule", {"date": day}, {"added_ids": ids}) for day, ids in list(by_day.items())[:3]]


def _auto_water(_args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    data = _result_data(result)
    inner = data.get("data") if isinstance(data.get("data"), dict) else data
    total = inner.get("total_ml")
    if isinstance(total, bool) or not isinstance(total, (int, float)):
        return []
    previous = inner.get("previous_ml")
    if isinstance(previous, bool) or not isinstance(previous, (int, float)):
        previous = total - _int_or(inner.get("added_ml"), 0)
    return [("water", {}, {"from_ml": max(0, int(previous)), "to_ml": max(0, int(total))})]


def _auto_tasks(kind: str) -> AutoPopup:
    def make(_args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
        ids = [str(item) for item in _result_data(result).get("task_ids") or [] if item]
        return [("task_list", {"filter": "pending"}, {kind: ids})] if ids else []
    return make


def _auto_places(_args: dict[str, Any], result: Any) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    data = _result_data(result)
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        return []
    near = data.get("near") if isinstance(data.get("near"), str) else ""
    params: dict[str, Any] = {"query": query}
    if near:
        params["near"] = near
    count = len(data.get("results") or [])
    return [("places", params, {"added_ids": [f"p{index}" for index in range(count)]})]


AUTO_POPUPS: dict[tuple[str, str], AutoPopup] = {
    ("task_tool", "create"): _auto_tasks("added_ids"),
    ("task_tool", "create_many"): _auto_tasks("added_ids"),
    ("task_tool", "toggle"): _auto_tasks("toggled_ids"),
    ("task_tool", "complete"): _auto_tasks("toggled_ids"),
    ("task_tool", "done"): _auto_tasks("toggled_ids"),
    ("task_tool", "update"): _auto_tasks("updated_ids"),
    # places_search não tem "action": a operação é vazia.
    ("places_search", ""): _auto_places,
    ("habit_tool", "create"): _auto_habits("added_ids"),
    ("habit_tool", "create_many"): _auto_habits("added_ids"),
    ("habit_tool", "check"): _auto_habits("checked_ids"),
    ("habit_tool", "check_many"): _auto_habits("checked_ids"),
    ("habit_tool", "update"): _auto_habits("updated_ids"),
    ("calendar", "create_reminder"): _auto_schedule,
    ("calendar", "create_many"): _auto_schedule,
    ("lifeos_tool", "add_water"): _auto_water,
    ("lifeos_tool", "set_water"): _auto_water,
}


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
    context = {"origin": origin, "run_id": run_id, "session_id": session_id, "animate": dict(animate or {})}
    data = spec.builder(clean, context)
    settings = get_popup_settings()
    title = data.get("title") if tid == "info" else spec.title
    return {
        "id": f"pop_{uuid.uuid4().hex}",
        "key": key or spec.key(clean, data),
        "template": tid,
        "version": POPUP_VERSION,
        "title": str(title or spec.title)[:80],
        "origin": origin if origin in POPUP_ORIGINS else "chat",
        "created_at": time.time(),
        "ttl_ms": 0 if spec.sticky else int(settings["ttl_seconds"]) * 1000,
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
    if getattr(result, "ok", True) is False:
        return []
    operation = str((args or {}).get("action") or "").strip().lower()
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
