"""Integração modular com o catálogo e os endpoints do Oxyy.

Oxyy mantém uma API compatível com OpenAI, mas os modelos de imagem, vídeo e
áudio possuem endpoints próprios. Este módulo concentra a descoberta do
catálogo para que a interface não precise conhecer detalhes da API.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


CAPABILITIES = ("chat", "image", "video", "tts", "stt", "embedding")

# Fallback usado quando a chave ainda não foi configurada ou o catálogo está
# temporariamente indisponível. Os ids são os exemplos documentados pelo Oxyy.
_FALLBACK_MODELS = [
    {"id": "gpt-4o-mini", "type": "chat", "provider": "OpenAI"},
    {"id": "llama-3.3-70b-instruct", "type": "chat", "provider": "Meta"},
    {"id": "gpt-4o", "type": "chat", "provider": "OpenAI"},
    {"id": "gpt-oss-120b", "type": "chat", "provider": "OpenAI"},
    {"id": "grok-4", "type": "chat", "provider": "xAI"},
    {"id": "dall-e-3", "type": "image", "provider": "OpenAI"},
    {"id": "flux.1-pro", "type": "image", "provider": "Black Forest Labs"},
    {"id": "imagen-4", "type": "image", "provider": "Google"},
    {"id": "veo-3", "type": "video", "provider": "Google"},
    {"id": "veo-3.1-fast", "type": "video", "provider": "Google"},
    {"id": "eleven_v3", "type": "tts", "provider": "ElevenLabs"},
    {"id": "tts-1-hd", "type": "tts", "provider": "OpenAI"},
    {"id": "gemini-tts", "type": "tts", "provider": "Google"},
    {"id": "whisper-1", "type": "stt", "provider": "OpenAI"},
    {"id": "gpt-4o-mini-transcribe", "type": "stt", "provider": "OpenAI"},
    {"id": "scribe_v1", "type": "stt", "provider": "ElevenLabs"},
    {"id": "gemini-embedding-001", "type": "embedding", "provider": "Google"},
]


def _base_url(value: str | None) -> str:
    return (value or "https://api.oxyy.ai/v1").rstrip("/")


def _provider_name(item: dict[str, Any]) -> str:
    for key in ("provider", "owned_by", "publisher", "organization"):
        value = item.get(key)
        if value:
            return str(value)
    model_id = str(item.get("id", ""))
    prefix = model_id.split("/", 1)[0] if "/" in model_id else model_id.split("-", 1)[0]
    return prefix.capitalize() if prefix else "Oxyy"


def infer_capability(item: dict[str, Any]) -> str:
    """Normaliza os formatos possíveis do catálogo para uma capacidade única."""
    raw = " ".join(
        str(item.get(key, ""))
        for key in ("type", "task", "modality", "category", "capability", "id")
    ).lower()
    if any(token in raw for token in ("embedding", "embed")):
        return "embedding"
    if any(token in raw for token in ("video", "veo", "kling", "runway", "sora")):
        return "video"
    if any(token in raw for token in ("image", "vision", "dall", "flux", "imagen")):
        return "image"
    if any(token in raw for token in ("speech", "tts", "text-to-speech", "eleven", "voice")):
        return "tts"
    if any(token in raw for token in ("transcrib", "stt", "whisper", "scribe")):
        return "stt"
    return "chat"


def normalize_models(payload: Any) -> list[dict[str, Any]]:
    """Converte a resposta de /models em registros seguros para o frontend."""
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in rows:
        if isinstance(item, str):
            item = {"id": item}
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", "")).strip()
        if not model_id or model_id in seen:
            continue
        seen.add(model_id)
        capability = infer_capability(item)
        result.append({
            "id": model_id,
            "name": str(item.get("name") or model_id),
            "provider": _provider_name(item),
            "type": capability,
            "context_length": item.get("context_length") or item.get("context_window"),
            "owned_by": str(item.get("owned_by") or ""),
        })
    return sorted(result, key=lambda row: (CAPABILITIES.index(row["type"]), row["provider"].lower(), row["id"].lower()))


def _fallback_catalog() -> list[dict[str, Any]]:
    return [dict(item, name=item["id"], context_length=None, owned_by="") for item in _FALLBACK_MODELS]


def fetch_models(api_key: str = "", base_url: str = "", timeout: float = 8.0) -> tuple[list[dict[str, Any]], bool, str | None]:
    """Busca o catálogo do Oxyy; retorna (modelos, remoto, erro).

    Nunca lança erro para a UI: sem chave ou em caso de indisponibilidade,
    devolve os modelos documentados como fallback e sinaliza ``remoto=False``.
    """
    if not api_key:
        return _fallback_catalog(), False, "Configure uma chave Oxyy para atualizar o catálogo."
    request = urllib.request.Request(
        f"{_base_url(base_url)}/models",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = normalize_models(payload)
        return (models or _fallback_catalog()), bool(models), None if models else "Catálogo vazio."
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, OSError) as exc:
        return _fallback_catalog(), False, str(exc)


def group_models(models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {capability: [] for capability in CAPABILITIES}
    for model in models:
        capability = model.get("type", "chat")
        if capability not in grouped:
            capability = "chat"
        grouped[capability].append(model)
    return grouped


def mask_key(key: str) -> str:
    value = str(key or "")
    if len(value) <= 8:
        return "••••" if value else ""
    return f"{value[:4]}…{value[-4:]}"
