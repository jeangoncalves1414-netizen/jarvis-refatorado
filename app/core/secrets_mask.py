"""Máscara de chaves de API para logs e console (MG14): só os 4 últimos caracteres aparecem."""
from __future__ import annotations


def mask_key(key: object) -> str:
    """Devolve ``…abcd`` (4 últimos caracteres); chaves curtas ou vazias viram ``…``."""
    value = str(key or "").strip()
    if len(value) <= 8:
        return "…"
    return f"…{value[-4:]}"


def scrub_key(text: object, *keys: object) -> str:
    """Troca qualquer ocorrência completa das chaves em ``text`` pela máscara."""
    result = str(text)
    for key in keys:
        value = str(key or "").strip()
        if len(value) > 8:
            result = result.replace(value, mask_key(value))
    return result
