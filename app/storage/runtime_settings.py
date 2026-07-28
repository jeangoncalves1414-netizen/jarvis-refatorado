from __future__ import annotations

import json
import os
from typing import Any

DATA_DIR = os.path.join(os.getcwd(), "data")
RUNTIME_SETTINGS_FILE = os.path.join(DATA_DIR, "runtime_settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

_VALID_PROVIDERS = {"gemini", "groq"}


def _read() -> dict[str, Any]:
    if not os.path.exists(RUNTIME_SETTINGS_FILE):
        return {}
    try:
        with open(RUNTIME_SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write(data: dict[str, Any]) -> None:
    with open(RUNTIME_SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_llm_provider(default: str = "gemini") -> str:
    data = _read()
    if "llm_provider" in data:
        provider = str(data["llm_provider"]).lower()
        return provider if provider in _VALID_PROVIDERS else "gemini"
    # Sem arquivo json: respeita a variável de ambiente LLM_PROVIDER
    env_provider = os.getenv("LLM_PROVIDER", default).lower()
    return env_provider if env_provider in _VALID_PROVIDERS else "gemini"


def set_llm_provider(provider: str) -> str:
    normalized = str(provider).lower()
    if normalized not in _VALID_PROVIDERS:
        raise ValueError(f"Provider inválido: {provider}")
    data = _read()
    data["llm_provider"] = normalized
    _write(data)
    os.environ["LLM_PROVIDER"] = normalized
    return normalized



def get_llm_settings(default_provider: str = "gemini") -> dict[str, Any]:
    data = _read()
    provider = get_llm_provider(default_provider)
    return {
        "llm_provider": provider,
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "")),
        "groq_configured": bool(os.getenv("GROQ_API_KEY", "")),
    }
