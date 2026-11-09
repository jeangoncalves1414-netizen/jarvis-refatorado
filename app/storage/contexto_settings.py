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


# ── Home Assistant (fase contexto 3) ───────────────────────────────────────
# Seção `home_assistant` (url, token) de runtime_settings.json, com fallback para
# HOME_ASSISTANT_URL/HOME_ASSISTANT_TOKEN. Sincroniza como as chaves de API. O token nunca
# sai por aqui de volta para a interface: só `token_masked`.
HA_SECTION = "home_assistant"
_MAX_TOKEN = 1000


def normalize_ha_url(value: Any) -> str:
    """`http(s)://host[:porta]`, sem credenciais nem caminho; barra final removida."""
    from urllib.parse import urlsplit

    text = str(value or "").strip().rstrip("/")
    if not text:
        return ""
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise ValueError("Endereço do Home Assistant inválido.") from None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise ValueError("Use um endereço como http://homeassistant.local:8123.")
    if "@" in parts.netloc:
        raise ValueError("Não coloque usuário ou senha no endereço do Home Assistant; use o token.")
    if parts.path or parts.query or parts.fragment:
        raise ValueError("Informe só o endereço do Home Assistant, sem caminho (ex.: http://192.168.0.10:8123).")
    if port is not None and not 0 < port < 65536:
        raise ValueError("Porta do Home Assistant inválida.")
    return f"{parts.scheme}://{parts.netloc}"


def get_home_assistant() -> dict[str, str]:
    """URL e token vigentes (arquivo primeiro, depois ambiente). Uso interno: contém o token."""
    import os

    saved = runtime_settings._read().get(HA_SECTION)
    saved = saved if isinstance(saved, dict) else {}
    url = str(saved.get("url") or "").strip() or os.getenv("HOME_ASSISTANT_URL", "").strip()
    token = str(saved.get("token") or "").strip() or os.getenv("HOME_ASSISTANT_TOKEN", "").strip()
    try:
        url = normalize_ha_url(url)
    except ValueError:
        url = ""
    return {"url": url, "token": token}


def mask_token(token: str) -> str:
    return f"••••{token[-4:]}" if len(token) >= 8 else ("••••" if token else "")


def home_assistant_public() -> dict[str, Any]:
    current = get_home_assistant()
    return {
        "url": current["url"],
        "configured": bool(current["url"] and current["token"]),
        "token_masked": mask_token(current["token"]),
    }


def set_home_assistant(values: dict[str, Any]) -> dict[str, Any]:
    """Grava url/token. Token vazio mantém o atual; ``clear: true`` apaga os dois."""
    if not isinstance(values, dict):
        raise ValueError("Configuração do Home Assistant inválida.")
    unknown = set(values) - {"url", "token", "clear"}
    if unknown:
        raise ValueError("Campo desconhecido na configuração do Home Assistant: " + ", ".join(sorted(unknown)) + ".")
    data = runtime_settings._read()
    saved = data.get(HA_SECTION) if isinstance(data.get(HA_SECTION), dict) else {}
    if values.get("clear") is True:
        data[HA_SECTION] = {"url": "", "token": ""}
        runtime_settings._write(data)
        return home_assistant_public()
    if "clear" in values and not isinstance(values["clear"], bool):
        raise ValueError("'clear' deve ser true ou false.")
    url = saved.get("url", "")
    if "url" in values:
        if not isinstance(values["url"], str):
            raise ValueError("O endereço do Home Assistant deve ser texto.")
        url = normalize_ha_url(values["url"])
        if not url:
            raise ValueError("Informe o endereço do Home Assistant.")
    token = str(saved.get("token") or "")
    if "token" in values:
        if not isinstance(values["token"], str):
            raise ValueError("O token do Home Assistant deve ser texto.")
        clean = values["token"].strip()
        if clean:
            if len(clean) > _MAX_TOKEN or any(ch.isspace() for ch in clean):
                raise ValueError("Token do Home Assistant inválido: cole o token de longa duração inteiro, sem espaços.")
            token = clean
    data[HA_SECTION] = {"url": url, "token": token}
    runtime_settings._write(data)
    return home_assistant_public()
