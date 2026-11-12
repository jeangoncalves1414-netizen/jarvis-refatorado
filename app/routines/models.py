"""Contrato de uma rotina (etapas, gatilhos, silêncio, tolerância) e validação com erros em português.

Rotinas circulam como dicionários JSON simples (o que vai para o SQLite e para a API). A validação
devolve só campos limpos; qualquer valor fora do contrato vira ``RoutineError`` com a mensagem que
a janela e a ferramenta mostram.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Any

MAX_STEPS = 20
MAX_TRIGGERS = 4
MAX_PARAMS_BYTES = 4096
MAX_NAME = 80
MAX_LABEL = 80
MAX_DELAY = 3600
MAX_RETRIES = 3
TIMEOUT_RANGE = (5, 600)
CATCH_UP_DEFAULT = 15
CATCH_UP_RANGE = (0, 720)
INTERVAL_RANGE = (5, 1440)

# Sem recursão (routine) e sem espera como etapa (use delay_before).
BLOCKED_STEP_TOOLS = frozenset({"routine", "wait"})
TIME_TRIGGERS = frozenset({"at", "daily", "weekdays", "weekly", "interval"})
TRIGGER_TYPES = TIME_TRIGGERS | {"voice", "command", "event"}
EVENT_KINDS = frozenset({"calendar_before", "app_started", "app_closed", "resource", "idle", "returned"})
ON_FAILURE = ("stop", "continue", "retry")
WEEK_DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Palavras "/" fixas do app (frontend/src/commands/registry.ts). Comando de rotina não pode repetir.
RESERVED_SLASHES = frozenset({
    "parar", "inicio", "conversas", "execucoes", "automacoes", "conhecimento", "integracoes", "estudos",
    "lifeos", "calendario", "painel", "metricas", "perfis", "config", "foco", "financas", "agua", "habitos",
    "hidratacao", "compromissos", "pendencias", "lugares", "nota", "nova", "voz", "ditado", "briefing",
    "pesquisa", "planejar", "clima", "controles", "backup", "sons", "cinema", "visao", "cameras", "rotinas",
})

_TIME = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_SLASH = re.compile(r"^[a-z0-9-]{2,30}$")
_RETRY_TEXT = re.compile(r"^retry\s*\(\s*(\d+)\s*\)$")
_JSON_TYPES: dict[str, tuple[type, ...]] = {
    "string": (str,), "integer": (int,), "number": (int, float), "boolean": (bool,), "array": (list,), "object": (dict,),
}


class RoutineError(ValueError):
    """Valor fora do contrato; a mensagem vai direto para a usuária."""


def normalize_text(text: Any) -> str:
    """Minúsculas, sem acentos e sem pontuação, espaços simples."""
    value = unicodedata.normalize("NFD", str(text or "")).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", value).split())


def _int(value: Any, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or (isinstance(value, float) and value != int(value)):
        if isinstance(value, str) and value.strip().isdigit():
            value = int(value.strip())
        else:
            raise RoutineError(f"{field} deve ser um número inteiro.")
    value = int(value)
    if not low <= value <= high:
        raise RoutineError(f"{field} deve estar entre {low} e {high}.")
    return value


def _time(value: Any, field: str) -> str:
    match = _TIME.match(str(value or "").strip())
    if not match:
        raise RoutineError(f"{field} deve estar no formato HH:MM (ex.: 08:00).")
    return f"{int(match.group(1)):02d}:{match.group(2)}"


# ── ferramentas e operações ─────────────────────────────────────────────────────

def _default_registry() -> Any:
    from app.agent.tools.registry import registry
    return registry


def operation_spec(tool: Any, metadata: Any) -> tuple[str | None, list[str]]:
    """Argumento que escolhe a operação e as operações aceitas (enum do schema ou mapa de risco)."""
    properties = ((getattr(tool, "parameters", None) or {}).get("properties") or {})
    action = properties.get("action") or {}
    if isinstance(action.get("enum"), list):
        return "action", [str(item) for item in action["enum"]]
    names = tuple(getattr(metadata, "operation_arguments", ()) or ())
    if names:
        enum = (properties.get(names[0]) or {}).get("enum")
        if isinstance(enum, list):
            return names[0], [str(item) for item in enum]
        return names[0], [operation for operation, _risk in getattr(metadata, "operation_risks", ())]
    return None, []


def step_tool_names(registry: Any = None) -> list[str]:
    """Ferramentas que podem virar etapa: registradas, no catálogo e no modo geral."""
    from app.agent.tools.catalog import TOOL_CATALOG
    from app.agent.tools.registry import GENERAL_TOOL_NAMES

    registry = registry or _default_registry()
    return sorted(
        name for name in GENERAL_TOOL_NAMES
        if name not in BLOCKED_STEP_TOOLS and name in TOOL_CATALOG and registry.get_tool(name) is not None
    )


def step_arguments(step: dict[str, Any], operation_argument: str | None) -> dict[str, Any]:
    """Argumentos executados: os parâmetros da etapa com a operação no argumento certo."""
    args = dict(step.get("params") or {})
    if operation_argument:
        args[operation_argument] = step.get("operation", "")
    return args


def _validate_params(raw: Any, tool: Any, operation_argument: str | None, label: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise RoutineError(f"{label}: os parâmetros devem ser um objeto.")
    try:
        size = len(json.dumps(raw, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError):
        raise RoutineError(f"{label}: os parâmetros devem ser JSON simples.") from None
    if size > MAX_PARAMS_BYTES:
        raise RoutineError(f"{label}: os parâmetros passam de 4 KB.")
    properties = ((getattr(tool, "parameters", None) or {}).get("properties") or {})
    clean: dict[str, Any] = {}
    for key, value in raw.items():
        if key == operation_argument:
            continue
        spec = properties.get(key)
        if spec is None:
            raise RoutineError(f"{label}: o parâmetro '{key}' não existe nesta ferramenta.")
        kinds = _JSON_TYPES.get(str(spec.get("type") or ""))
        if kinds and value is not None:
            wrong_bool = isinstance(value, bool) and bool not in kinds
            if wrong_bool or not isinstance(value, kinds):
                raise RoutineError(f"{label}: o parâmetro '{key}' tem tipo inválido.")
        enum = spec.get("enum")
        if isinstance(enum, list) and value not in enum:
            raise RoutineError(f"{label}: o parâmetro '{key}' deve ser um de: {', '.join(map(str, enum))}.")
        clean[str(key)] = value
    return clean


def _parse_failure(step: dict[str, Any], label: str) -> tuple[str, int]:
    raw = str(step.get("on_failure") or "stop").strip().lower()
    retries = step.get("retries")
    match = _RETRY_TEXT.match(raw)
    if match:
        raw, retries = "retry", int(match.group(1))
    if raw not in ON_FAILURE:
        raise RoutineError(f"{label}: 'se falhar' deve ser parar (stop), continuar (continue) ou tentar de novo (retry).")
    if raw != "retry":
        return raw, 0
    return raw, _int(1 if retries in (None, "", 0) else retries, f"{label}: tentativas", 1, MAX_RETRIES)


def validate_step(raw: Any, index: int, registry: Any) -> dict[str, Any]:
    from app.agent.tools.catalog import TOOL_CATALOG

    label = f"Etapa {index + 1}"
    if not isinstance(raw, dict):
        raise RoutineError(f"{label}: formato inválido.")
    tool_name = str(raw.get("tool") or "").strip()
    if tool_name in BLOCKED_STEP_TOOLS:
        raise RoutineError(
            f"{label}: a ferramenta '{tool_name}' não pode ser etapa de rotina"
            + (" (use 'Esperar antes' na etapa seguinte)." if tool_name == "wait" else ".")
        )
    tool = registry.get_tool(tool_name) if tool_name else None
    if tool is None or tool_name not in TOOL_CATALOG or tool_name not in step_tool_names(registry):
        valid_tools = ', '.join(step_tool_names(registry)[:25])
        raise RoutineError(f"{label}: ferramenta desconhecida '{tool_name or '(vazia)'}'. Use uma destas: {valid_tools}.")
    metadata = registry.get_tool_metadata(tool_name)
    argument, operations = operation_spec(tool, metadata)
    operation = str(raw.get("operation") or "").strip().lower()
    if argument:
        if not operation and isinstance(raw.get("params"), dict):
            operation = str(raw["params"].get(argument) or "").strip().lower()
        if operation not in operations:
            raise RoutineError(f"{label}: operação '{operation or '(vazia)'}' não existe em {tool_name}. Use: {', '.join(operations)}.")
    else:
        operation = ""
    params = _validate_params(raw.get("params"), tool, argument, label)
    on_failure, retries = _parse_failure(raw, label)
    timeout = raw.get("timeout")
    if timeout in (None, "", 0):
        timeout = None
    else:
        timeout = _int(timeout, f"{label}: tempo limite (s)", *TIMEOUT_RANGE)
    step_label = " ".join(str(raw.get("label") or "").split())[:MAX_LABEL] or default_step_label(tool_name, operation, params)
    return {
        "id": str(raw.get("id") or f"s{index + 1}")[:20],
        "label": step_label,
        "tool": tool_name,
        "operation": operation,
        "params": params,
        "delay_before": _int(raw.get("delay_before") or 0, f"{label}: esperar antes (s)", 0, MAX_DELAY),
        "on_failure": on_failure,
        "retries": retries,
        "timeout": timeout,
    }


_TOOL_LABELS = {
    "open_windows_app": "Abrir", "spotify": "Spotify", "web_search": "Web", "system_control": "Sistema",
    "timer": "Timer", "calendar": "Agenda", "task_tool": "Tarefa", "habit_tool": "Hábito",
}


def default_step_label(tool: str, operation: str, params: dict[str, Any]) -> str:
    target = next((str(params[key]) for key in ("app_name", "query", "url", "title", "name", "label") if params.get(key)), "")
    if tool == "open_windows_app" and operation == "open":
        text = f"Abrir {target}".strip()
    elif tool == "spotify" and operation == "search_play":
        text = f"Tocar {target} no Spotify".strip()
    elif tool == "web_search" and operation == "open_url":
        text = f"Abrir {target}".strip()
    else:
        text = " ".join(part for part in (_TOOL_LABELS.get(tool, tool), operation, target) if part)
    return text[:MAX_LABEL]


# ── gatilhos ────────────────────────────────────────────────────────────────────

def validate_trigger(raw: Any, index: int) -> dict[str, Any]:
    label = f"Gatilho {index + 1}"
    if not isinstance(raw, dict):
        raise RoutineError(f"{label}: formato inválido.")
    kind = str(raw.get("type") or "").strip().lower()
    if kind not in TRIGGER_TYPES:
        raise RoutineError(f"{label}: tipo desconhecido '{kind or '(vazio)'}'.")
    if kind == "at":
        text = str(raw.get("datetime") or "").strip()
        try:
            moment = datetime.fromisoformat(text)
        except ValueError:
            raise RoutineError(f"{label}: data e hora devem estar no formato AAAA-MM-DDTHH:MM.") from None
        return {"type": "at", "datetime": moment.replace(tzinfo=None, second=0, microsecond=0).isoformat(timespec="minutes")}
    if kind in ("daily", "weekdays"):
        return {"type": kind, "time": _time(raw.get("time"), f"{label}: hora")}
    if kind == "weekly":
        days = raw.get("days")
        if isinstance(days, str):
            days = [part.strip() for part in days.split(",")]
        if not isinstance(days, list) or not days:
            raise RoutineError(f"{label}: escolha pelo menos um dia da semana.")
        clean = []
        for day in days:
            value = str(day or "").strip().lower()[:3]
            if value not in WEEK_DAYS:
                raise RoutineError(f"{label}: dia inválido '{day}'. Use mon, tue, wed, thu, fri, sat ou sun.")
            if value not in clean:
                clean.append(value)
        return {"type": "weekly", "days": sorted(clean, key=WEEK_DAYS.index), "time": _time(raw.get("time"), f"{label}: hora")}
    if kind == "interval":
        return {"type": "interval", "minutes": _int(raw.get("minutes"), f"{label}: intervalo (min)", *INTERVAL_RANGE)}
    if kind == "voice":
        phrase = normalize_text(raw.get("phrase"))
        if not 3 <= len(phrase) <= 80:
            raise RoutineError(f"{label}: a frase de voz deve ter entre 3 e 80 letras.")
        return {"type": "voice", "phrase": phrase}
    if kind == "command":
        slash = str(raw.get("slash") or "").strip().lstrip("/").lower()
        if not _SLASH.match(slash):
            raise RoutineError(f"{label}: o comando deve ter de 2 a 30 letras minúsculas, números ou hífen (ex.: foco-manha).")
        if slash in RESERVED_SLASHES:
            raise RoutineError(f"{label}: o comando /{slash} já existe no app; escolha outro nome.")
        return {"type": "command", "slash": slash}

    if kind == "event":
        ev = str(raw.get("event") or "").strip().lower()
        if ev not in EVENT_KINDS:
            raise RoutineError(f"{label}: tipo de evento desconhecido '{ev}'.")
        mode = str(raw.get("mode") or "alert").strip().lower()
        if mode not in ("alert", "run"):
            raise RoutineError(f"{label}: modo de evento deve ser alert ou run.")
        cooldown = _int(raw.get("cooldown_minutes") or 30, f"{label}: intervalo entre avisos (min)", 1, 1440)
        window = None
        if raw.get("window"):
            w = raw["window"]
            if not isinstance(w, dict) or not w.get("start") or not w.get("end"):
                raise RoutineError(f"{label}: janela de horário deve ter início e fim.")
            window = {"start": _time(w["start"], f"{label}: janela início"), "end": _time(w["end"], f"{label}: janela fim")}
        raw_params = raw.get("params") or {}
        if not isinstance(raw_params, dict):
            raise RoutineError(f"{label}: parâmetros do evento devem ser um objeto.")
        params: dict[str, Any] = {}
        if ev == "calendar_before":
            params["minutes"] = _int(raw_params.get("minutes") or 15, f"{label}: minutos antes", 1, 1440)
        elif ev in ("app_started", "app_closed"):
            app_name = str(raw_params.get("app_name") or "").strip()
            if not app_name:
                raise RoutineError(f"{label}: informe o nome do programa (app_name).")
            params["app_name"] = app_name
        elif ev == "resource":
            metric = str(raw_params.get("metric") or "cpu").strip().lower()
            if metric not in ("cpu", "ram", "disk"):
                raise RoutineError(f"{label}: métrica deve ser cpu, ram ou disk.")
            params["metric"] = metric
            params["threshold"] = _int(raw_params.get("threshold") or 90, f"{label}: limiar (%)", 50, 99)
            params["for_seconds"] = _int(raw_params.get("for_seconds") or 120, f"{label}: duração (s)", 0, 3600)
        elif ev in ("idle", "returned"):
            params["minutes"] = _int(raw_params.get("minutes") or 15, f"{label}: minutos ocioso", 1, 720)

        result_ev: dict[str, Any] = {"type": "event", "event": ev, "params": params, "mode": mode, "cooldown_minutes": cooldown}
        if window:
            result_ev["window"] = window
        return result_ev


def validate_triggers(raw: Any) -> list[dict[str, Any]]:
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise RoutineError("Os gatilhos devem ser uma lista.")
    if len(raw) > MAX_TRIGGERS:
        raise RoutineError(f"Uma rotina tem no máximo {MAX_TRIGGERS} gatilhos.")
    triggers = [validate_trigger(item, index) for index, item in enumerate(raw)]
    groups = {"horário": TIME_TRIGGERS, "frase de voz": {"voice"}, "comando": {"command"}, "evento": {"event"}}
    for name, kinds in groups.items():
        if sum(1 for item in triggers if item["type"] in kinds) > 1:
            raise RoutineError(f"Uma rotina tem no máximo 1 gatilho de {name}.")
    return triggers


def validate_quiet(raw: Any) -> dict[str, str] | None:
    if raw in (None, "", {}):
        return None
    if not isinstance(raw, dict):
        raise RoutineError("O horário de silêncio deve ter início e fim.")
    start, end = _time(raw.get("start"), "Silêncio: início"), _time(raw.get("end"), "Silêncio: fim")
    if start == end:
        raise RoutineError("O horário de silêncio precisa de início e fim diferentes.")
    return {"start": start, "end": end}


def describe_steps(routine: dict[str, Any], limit: int = 3) -> list[str]:
    """"1. Abrir chrome", "2. após 30 s: Tocar Foco no Spotify" (no máximo ``limit`` linhas + "e mais N")."""
    steps = list(routine.get("steps") or [])
    lines = []
    for index, step in enumerate(steps[:limit]):
        delay = int(step.get("delay_before") or 0)
        prefix = f"após {delay} s: " if delay else ""
        lines.append(f"{index + 1}. {prefix}{step.get('label') or step.get('tool')}"[:120])
    if len(steps) > limit:
        lines.append(f"e mais {len(steps) - limit} etapa(s)")
    return lines


def time_trigger(routine: dict[str, Any]) -> dict[str, Any] | None:
    return next((item for item in routine.get("triggers") or [] if item.get("type") in TIME_TRIGGERS), None)


def validate_routine(payload: Any, registry: Any = None) -> dict[str, Any]:
    """Campos editáveis limpos de uma rotina: name, enabled, steps, triggers, quiet, catch_up_minutes."""
    if not isinstance(payload, dict):
        raise RoutineError("A rotina deve ser um objeto JSON.")
    registry = registry or _default_registry()
    name = " ".join(str(payload.get("name") or "").split())
    if not name:
        raise RoutineError("Dê um nome para a rotina.")
    if len(name) > MAX_NAME:
        raise RoutineError(f"O nome da rotina deve ter no máximo {MAX_NAME} caracteres.")
    steps_raw = payload.get("steps")
    if not isinstance(steps_raw, list) or not steps_raw:
        raise RoutineError("A rotina precisa de pelo menos uma etapa.")
    if len(steps_raw) > MAX_STEPS:
        raise RoutineError(f"Uma rotina tem no máximo {MAX_STEPS} etapas.")
    steps = [validate_step(item, index, registry) for index, item in enumerate(steps_raw)]
    seen: set[str] = set()
    for index, step in enumerate(steps):
        if step["id"] in seen:
            step["id"] = f"s{index + 1}"
        seen.add(step["id"])
    enabled = payload.get("enabled", True)
    if not isinstance(enabled, bool):
        raise RoutineError("'Ativa' deve ser verdadeiro ou falso.")
    triggers = validate_triggers(payload.get("triggers"))
    if any(item["type"] == "event" for item in triggers):
        for step in steps:
            tool = str(step.get("tool") or "").lower()
            op = str(step.get("operation") or "").lower()
            if (tool == "open_windows_app" and op == "close") or re.search(r"\b(close|kill|terminate|end_task)\b", op):
                raise RoutineError("Gatilho automático não pode encerrar programas.")
    catch_up = payload.get("catch_up_minutes")
    return {
        "name": name,
        "enabled": enabled,
        "steps": steps,
        "triggers": triggers,
        "quiet": validate_quiet(payload.get("quiet", payload.get("quiet_hours"))),
        "catch_up_minutes": CATCH_UP_DEFAULT if catch_up in (None, "") else _int(catch_up, "Tolerância (min)", *CATCH_UP_RANGE),
    }
