"""Configurações do contexto situacional (fase 1 do contexto).

Ficam na seção `situational_context` de runtime_settings.json, gravadas pelas mesmas
funções `_read`/`_write` do runtime_settings (sincronizam como as outras seções).
"""
from __future__ import annotations

from typing import Any

from app.storage import runtime_settings

SECTION = "situational_context"
SOURCE_KEYS = ("datetime", "calendar", "window", "media", "lifeos", "tasks", "routines", "pc")
SOURCE_LABELS = {
    "datetime": "Data e hora",
    "calendar": "Próximo compromisso",
    "window": "Janela em primeiro plano",
    "media": "Música tocando",
    "lifeos": "Água e hábitos",
    "tasks": "Tarefas pendentes",
    "routines": "Rotinas em andamento",
    "pc": "Estado do PC",
}
CONTEXT_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "show_in_chat": True,
    "send_window_titles": False,
    "sources": {key: True for key in SOURCE_KEYS},
}
_FLAG_LABELS = {
    "enabled": "Usar contexto da situação",
    "show_in_chat": "Mostrar 'Contexto usado' no chat",
    "send_window_titles": "Enviar títulos de janelas",
}


def get_context_settings() -> dict[str, Any]:
    saved = runtime_settings._read().get(SECTION)
    saved = saved if isinstance(saved, dict) else {}
    result: dict[str, Any] = {}
    for key in _FLAG_LABELS:
        value = saved.get(key, CONTEXT_DEFAULTS[key])
        result[key] = value if isinstance(value, bool) else CONTEXT_DEFAULTS[key]
    sources = saved.get("sources")
    sources = sources if isinstance(sources, dict) else {}
    result["sources"] = {
        key: sources[key] if isinstance(sources.get(key), bool) else True for key in SOURCE_KEYS
    }
    return result


def set_context_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Valida tudo antes de gravar; valor inválido não altera nada."""
    if not isinstance(values, dict):
        raise ValueError("Configuração do contexto inválida.")
    unknown = set(values) - set(CONTEXT_DEFAULTS)
    if unknown:
        raise ValueError("Campo desconhecido na configuração do contexto: " + ", ".join(sorted(unknown)) + ".")
    current = get_context_settings()
    for key, label in _FLAG_LABELS.items():
        if key in values:
            if not isinstance(values[key], bool):
                raise ValueError(f"{label} deve ser ligado ou desligado (true/false).")
            current[key] = values[key]
    if "sources" in values:
        sources = values["sources"]
        if not isinstance(sources, dict):
            raise ValueError("As fontes do contexto devem ser uma lista de chaves ligadas ou desligadas.")
        unknown_sources = set(sources) - set(SOURCE_KEYS)
        if unknown_sources:
            raise ValueError("Fonte de contexto desconhecida: " + ", ".join(sorted(unknown_sources)) + ".")
        for key, value in sources.items():
            if not isinstance(value, bool):
                raise ValueError(f"A fonte '{SOURCE_LABELS[key]}' deve ser ligada ou desligada (true/false).")
            current["sources"][key] = value
    data = runtime_settings._read()
    data[SECTION] = current
    runtime_settings._write(data)
    return get_context_settings()
