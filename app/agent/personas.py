"""Sistema de Personas Modular do Jarvis.

Permite configurar:
- Nome do assistente (ex: Jarvis, Sexta-Feira, etc.)
- Tom de resposta (amigável, formal, bem-humorado, militar, sarcástico leve)
- Desafio matinal configurável (ativado/desativado por flag e texto descritivo)
- Regras e instruções específicas da persona adicionadas ao prompt do sistema

Persistência em: runtime_settings.DATA_DIR / persona_config.json
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from app.storage.runtime_settings import DATA_DIR

PERSONA_CONFIG_FILE = os.path.join(DATA_DIR, "persona_config.json")

VALID_TONES = {
    "amigável": "Caloroso, empático, encorajador e prestativo. Comunicação acessível e acolhedora.",
    "formal": "Polido, profissional, preciso e sóbrio. Comunicação corporativa de alto padrão e sem gírias.",
    "bem-humorado": "Descontraído, espirituoso, animado e leve. Humor amigável e entusiasmo positivo.",
    "militar": "Disciplinado, conciso, tático e direto ao ponto. Foco total em execução, metas e clareza absoluta.",
    "sarcástico leve": "Inteligente, espirituoso, com ironia sutil e elegância britânica (estilo clássico de Jarvis), mantendo fidelidade e eficiência máximas.",
}

DEFAULT_PERSONA: dict[str, Any] = {
    "name": "Jarvis",
    "tone": "amigável",
    "morning_challenge": {
        "enabled": True,
        "text": "10 polichinelos e 10 flexões",
    },
    "custom_rules": "",
}

_lock = threading.RLock()


def _get_config_path() -> str:
    # Permite override em testes se necessário via variável de ambiente
    custom_dir = os.environ.get("JARVIS_DATA_DIR")
    if custom_dir:
        os.makedirs(custom_dir, exist_ok=True)
        return os.path.join(custom_dir, "persona_config.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    return PERSONA_CONFIG_FILE


def _sanitize_name(value: Any) -> str:
    name = " ".join(str(value or "").strip().split())
    if not name:
        return DEFAULT_PERSONA["name"]
    return name[:50]


def _sanitize_tone(value: Any) -> str:
    tone = str(value or "").strip().lower()
    if tone in VALID_TONES:
        return tone
    # Mapeamentos flexíveis
    synonyms = {
        "amigavel": "amigável",
        "friendly": "amigável",
        "sarcastico": "sarcástico leve",
        "sarcastico leve": "sarcástico leve",
        "ironico": "sarcástico leve",
        "humorado": "bem-humorado",
        "bem humorado": "bem-humorado",
        "engracado": "bem-humorado",
        "profissional": "formal",
        "tatica": "militar",
        "tatico": "militar",
    }
    return synonyms.get(tone, "amigável")


def _sanitize_challenge(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return dict(DEFAULT_PERSONA["morning_challenge"])
    enabled = bool(value.get("enabled", True))
    text = " ".join(str(value.get("text") or "").strip().split())
    if not text:
        text = DEFAULT_PERSONA["morning_challenge"]["text"]
    return {
        "enabled": enabled,
        "text": text[:200],
    }


def _sanitize_rules(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        return "\n".join(str(item).strip() for item in value if str(item).strip())[:2000]
    return str(value or "").strip()[:2000]


def get_persona() -> dict[str, Any]:
    """Retorna as configurações atuais da Persona."""
    path = _get_config_path()
    with _lock:
        if not os.path.exists(path):
            return dict(DEFAULT_PERSONA)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return dict(DEFAULT_PERSONA)
            return {
                "name": _sanitize_name(data.get("name")),
                "tone": _sanitize_tone(data.get("tone")),
                "morning_challenge": _sanitize_challenge(data.get("morning_challenge")),
                "custom_rules": _sanitize_rules(data.get("custom_rules")),
            }
        except (json.JSONDecodeError, OSError):
            return dict(DEFAULT_PERSONA)


def update_persona(updates: dict[str, Any]) -> dict[str, Any]:
    """Atualiza as configurações da Persona com validação e persistência."""
    if not isinstance(updates, dict):
        raise ValueError("Dados de persona devem ser um dicionário.")

    current = get_persona()
    path = _get_config_path()

    with _lock:
        if "name" in updates:
            current["name"] = _sanitize_name(updates["name"])

        if "tone" in updates:
            current["tone"] = _sanitize_tone(updates["tone"])

        if "morning_challenge" in updates:
            current["morning_challenge"] = _sanitize_challenge(updates["morning_challenge"])
        else:
            # Suporte a campos planos tipo morning_challenge_enabled / morning_challenge_text
            challenge = dict(current["morning_challenge"])
            if "morning_challenge_enabled" in updates:
                challenge["enabled"] = bool(updates["morning_challenge_enabled"])
            if "morning_challenge_text" in updates:
                text = " ".join(str(updates["morning_challenge_text"] or "").strip().split())
                if text:
                    challenge["text"] = text[:200]
            current["morning_challenge"] = challenge

        if "custom_rules" in updates:
            current["custom_rules"] = _sanitize_rules(updates["custom_rules"])

        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(current, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)

    # Mantém consistência com o perfil do agente existente em runtime_settings (opcional)
    try:
        from app.storage import runtime_settings
        profile = runtime_settings.get_agent_profile()
        if profile.get("name") != current["name"]:
            runtime_settings.set_agent_profile({**profile, "name": current["name"]})
    except Exception:
        pass

    return current


def reset_persona() -> dict[str, Any]:
    """Restaura a persona para o padrão de fábrica."""
    return update_persona(dict(DEFAULT_PERSONA))


def get_persona_context() -> str:
    """Gera o bloco de prompt estruturado com as diretrizes da persona ativa."""
    p = get_persona()
    tone_key = p["tone"]
    tone_desc = VALID_TONES.get(tone_key, VALID_TONES["amigável"])

    lines = [
        "## Persona e Identidade Ativa",
        f"- Nome: {p['name']}",
        f"- Tom de resposta ({tone_key}): {tone_desc}",
    ]

    if p["morning_challenge"].get("enabled"):
        lines.append(f"- Desafio matinal ativo: \"{p['morning_challenge']['text']}\" (incentive o cumprimento quando falar de rotina matinal).")

    if p.get("custom_rules"):
        lines.append(f"- Diretrizes específicas da persona:\n{p['custom_rules']}")

    return "\n".join(lines)
