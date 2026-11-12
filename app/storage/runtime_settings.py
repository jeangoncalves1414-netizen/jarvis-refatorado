from __future__ import annotations

import json
import os
import hashlib
import tempfile
import time
from typing import Any

DATA_DIR = os.path.join(os.getcwd(), "data")
RUNTIME_SETTINGS_FILE = os.path.join(DATA_DIR, "runtime_settings.json")

os.makedirs(DATA_DIR, exist_ok=True)

_VALID_PROVIDERS = {"gemini", "groq", "oxyy"}
_VALID_TTS_PROVIDERS = {"fish", "gemini", "edge", "oxyy"}
_VALID_STT_PROVIDERS = {"local", "groq", "oxyy", "google", "whisper_local"}
_OXYY_MODEL_DEFAULTS = {
    "chat": "gpt-4o-mini",
    "tts": "tts-1-hd",
    "tts_voice": "alloy",
    "stt": "whisper-1",
    "image": "dall-e-3",
    "video": "veo-3",
    "embedding": "gemini-embedding-001",
}


def _read() -> dict[str, Any]:
    if not os.path.exists(RUNTIME_SETTINGS_FILE):
        return {}
    try:
        with open(RUNTIME_SETTINGS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        keys = data.get("api_keys", {})
        if isinstance(keys, dict) and any(isinstance(v, str) and v for v in keys.values()):
            _write_raw(data)  # primeira abertura migra valores legados
            with open(RUNTIME_SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        from app.storage import credential_store as vault
        refs = {}
        keys = data.get("api_keys") if isinstance(data.get("api_keys"), dict) else {}
        for name, value in list(keys.items()):
            if isinstance(value, dict) and isinstance(value.get("credential_refs"), list):
                refs[name] = value
                try:
                    data["api_keys"][name] = ",".join(vault.load_key(ref) or "" for ref in value["credential_refs"])
                except vault.CredentialUnavailable:
                    vault.warn_unavailable()
                    data["api_keys"][name] = ""
        if refs:
            data["_credential_refs"] = refs
        return data
    except (json.JSONDecodeError, OSError):
        return {}


# Carimbos por campo para a sincronização com a nuvem. Cada campo plano
# ("api_keys.groq", "llm_provider", "agent_profile.name"...) guarda o instante
# da última alteração local; a mesclagem entre dispositivos usa esses carimbos.
SYNC_META_KEY = "_field_ts"
_MISSING = object()


def flatten_settings(data: dict[str, Any]) -> dict[str, Any]:
    """Achata o JSON em até dois níveis: 'secao.campo' (valores internos ficam inteiros)."""
    flat: dict[str, Any] = {}
    for key, value in data.items():
        if key in (SYNC_META_KEY, "_credential_refs"):
            continue
        if isinstance(value, dict) and value:
            for sub, sub_value in value.items():
                flat[f"{key}.{sub}"] = sub_value
        else:
            flat[key] = value
    return flat


def unflatten_into(data: dict[str, Any], path: str, value: Any) -> None:
    section, dot, field = path.partition(".")
    if not dot:
        data[section] = value
        return
    bucket = data.get(section)
    if not isinstance(bucket, dict):
        bucket = {}
        data[section] = bucket
    bucket[field] = value


def _write_raw(data: dict[str, Any]) -> None:
    from app.storage import credential_store as vault
    encoded = dict(data)
    old_refs = encoded.pop("_credential_refs", {})
    keys = dict(data.get("api_keys")) if isinstance(data.get("api_keys"), dict) else {}
    scope = hashlib.sha256(os.path.abspath(RUNTIME_SETTINGS_FILE).casefold().encode()).hexdigest()[:16]
    for name, value in keys.items():
        if not isinstance(value, str):
            continue
        previous = old_refs.get(name, {}).get("credential_refs", [])
        try:
            if value:
                references = []
                for index, key in enumerate(part.strip() for part in value.replace("\n", ",").split(",") if part.strip()):
                    ref = f"{scope}/{name}/{index}"
                    vault.save_key(ref, key)
                    if vault.load_key(ref) != key:
                        raise vault.CredentialUnavailable("A credencial não foi confirmada.")
                    references.append(ref)
                keys[name] = {"credential_refs": references}
            else:
                # Se o cofre ficou indisponível, mantém a referência ainda recuperável.
                for ref in previous:
                    vault.load_key(ref)
                for ref in previous:
                    vault.delete_key(ref)
        except vault.CredentialUnavailable:
            vault.warn_unavailable()
            if not value and previous:
                keys[name] = {"credential_refs": previous}
    if "api_keys" in data:
        encoded["api_keys"] = keys
    folder = os.path.dirname(os.path.abspath(RUNTIME_SETTINGS_FILE))
    fd, temporary = tempfile.mkstemp(dir=folder, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(encoded, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, RUNTIME_SETTINGS_FILE)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write(data: dict[str, Any]) -> None:
    previous = _read()
    stamps = previous.get(SYNC_META_KEY) if isinstance(previous.get(SYNC_META_KEY), dict) else {}
    stamps = dict(stamps)
    old_flat = flatten_settings(previous)
    now = int(time.time() * 1000)
    for path, value in flatten_settings(data).items():
        if old_flat.get(path, _MISSING) != value:
            stamps[path] = now
    data[SYNC_META_KEY] = stamps
    _write_raw(data)


def sync_api_keys_to_env() -> None:
    """Carrega chaves salvas em runtime_settings.json para as variáveis de ambiente.
    
    NOTE: This function should be called explicitly after the application is fully
    initialized, not at module import time, to avoid race conditions with file I/O.
    """
    data = _read()
    keys = data.get("api_keys", {})
    if isinstance(keys, dict):
        mapping = {
            "oxyy": ("OXYY_API_KEY", "OXYY_API_KEYS"),
            "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
            "gemini": ("GEMINI_API_KEY", "GEMINI_API_KEYS"),
            "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"),
            "fish": ("FISH_API_KEY", "FISH_API_KEYS"),
            "google_places": ("GOOGLE_PLACES_API_KEY", "GOOGLE_PLACES_API_KEYS"),
        }
        for key_id, (env_key, env_keys) in mapping.items():
            val = str(keys.get(key_id) or "").strip()
            if val:
                os.environ[env_key] = val
                os.environ[env_keys] = val


def get_api_keys() -> dict[str, str]:
    """Retorna as chaves de API atualmente configuradas (mascaradas e brutas para gerenciamento).
    Retorna todas as chaves separadas por vírgula quando disponíveis no ambiente.
    """
    data = _read()
    saved = data.get("api_keys", {}) if isinstance(data.get("api_keys"), dict) else {}
    mapping = {
        "oxyy": ("OXYY_API_KEY", "OXYY_API_KEYS"),
        "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
        "gemini": ("GEMINI_API_KEY", "GEMINI_API_KEYS"),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"),
        "fish": ("FISH_API_KEY", "FISH_API_KEYS"),
        "google_places": ("GOOGLE_PLACES_API_KEY", "GOOGLE_PLACES_API_KEYS"),
    }
    result = {}
    for key_id, (env_key, env_keys) in mapping.items():
        # Prioriza chave salva no runtime_settings.json
        if saved.get(key_id):
            result[key_id] = str(saved[key_id]).strip()
        else:
            # Se não tiver salva, pega do ambiente (suporta múltiplas chaves separadas por vírgula)
            env_val = os.getenv(env_keys) or os.getenv(env_key) or ""
            if env_val:
                # Normaliza as chaves (separadas por vírgula ou newline)
                keys = [k.strip() for k in env_val.replace("\n", ",").split(",") if k.strip()]
                result[key_id] = ",".join(keys)
            else:
                result[key_id] = ""
    return result


def set_api_keys(keys: dict[str, str], settings_obj: Any | None = None) -> dict[str, str]:
    """Salva chaves de API no runtime_settings.json e aplica ao ambiente.
    Suporta múltiplas chaves separadas por vírgula.
    """
    if not isinstance(keys, dict):
        raise ValueError("keys deve ser um dicionário.")
    data = _read()
    current = data.get("api_keys", {}) if isinstance(data.get("api_keys"), dict) else {}
    allowed = {"oxyy", "groq", "gemini", "openrouter", "fish", "google_places"}
    mapping = {
        "oxyy": ("OXYY_API_KEY", "OXYY_API_KEYS"),
        "groq": ("GROQ_API_KEY", "GROQ_API_KEYS"),
        "gemini": ("GEMINI_API_KEY", "GEMINI_API_KEYS"),
        "openrouter": ("OPENROUTER_API_KEY", "OPENROUTER_API_KEYS"),
        "fish": ("FISH_API_KEY", "FISH_API_KEYS"),
        "google_places": ("GOOGLE_PLACES_API_KEY", "GOOGLE_PLACES_API_KEYS"),
    }
    for key_id, val in keys.items():
        if key_id in allowed:
            clean_val = str(val or "").strip()
            # Normaliza as chaves (separadas por vírgula ou newline)
            if clean_val:
                keys_list = [k.strip() for k in clean_val.replace("\n", ",").split(",") if k.strip()]
                clean_val = ",".join(keys_list)
            current[key_id] = clean_val
            env_key, env_keys = mapping[key_id]
            # Aplica tanto a versão singular quanto plural
            os.environ[env_key] = clean_val
            os.environ[env_keys] = clean_val
    data["api_keys"] = current
    _write(data)
    
    # Update in-memory Settings object if provided
    if settings_obj:
        sync_settings_to_obj(settings_obj)
    
    return get_api_keys()


def sync_settings_to_obj(settings_obj: Any) -> None:
    """Sincroniza runtime_settings.json e env para o objeto Settings em memória.
    
    Args:
        settings_obj: The Settings dataclass instance to update
    """
    data = _read()
    
    # Sync API keys to Settings object
    keys = data.get("api_keys", {}) if isinstance(data.get("api_keys"), dict) else {}
    
    # Update singular and plural fields
    if "groq" in keys:
        groq_val = str(keys["groq"]).strip()
        settings_obj.groq_api_key = groq_val.split(",")[0].strip() if groq_val else ""
        settings_obj.groq_api_keys = [k.strip() for k in groq_val.replace("\n", ",").split(",") if k.strip()]
    
    if "gemini" in keys:
        gemini_val = str(keys["gemini"]).strip()
        settings_obj.gemini_api_key = gemini_val.split(",")[0].strip() if gemini_val else ""
        settings_obj.gemini_api_keys = [k.strip() for k in gemini_val.replace("\n", ",").split(",") if k.strip()]
    
    if "oxyy" in keys:
        oxyy_val = str(keys["oxyy"]).strip()
        settings_obj.oxyy_api_key = oxyy_val.split(",")[0].strip() if oxyy_val else ""
        settings_obj.oxyy_api_keys = [k.strip() for k in oxyy_val.replace("\n", ",").split(",") if k.strip()]
    
    if "fish" in keys:
        fish_val = str(keys["fish"]).strip()
        settings_obj.fish_api_key = fish_val
    
    # Sync providers
    if "llm_provider" in data:
        settings_obj.llm_provider = str(data["llm_provider"]).lower()
    if "tts_provider" in data:
        settings_obj.tts_provider = str(data["tts_provider"]).lower()
    if "stt_provider" in data:
        settings_obj.stt_provider = str(data["stt_provider"]).lower()
    
    # Vozes dentro de cada provedor TTS (item VZ1)
    voices = data.get("tts_voices") if isinstance(data.get("tts_voices"), dict) else {}
    if voices.get("fish_reference_id"):
        settings_obj.fish_reference_id = str(voices["fish_reference_id"])
    if voices.get("gemini"):
        settings_obj.tts_gemini_voice = str(voices["gemini"])
    if voices.get("edge"):
        settings_obj.tts_voice = str(voices["edge"])
    # Sync Oxyy models
    if isinstance(data.get("oxyy_models"), dict):
        oxyy_models = data["oxyy_models"]
        settings_obj.oxyy_chat_model = str(oxyy_models.get("chat", settings_obj.oxyy_chat_model))
        settings_obj.oxyy_tts_model = str(oxyy_models.get("tts", settings_obj.oxyy_tts_model))
        settings_obj.oxyy_tts_voice = str(oxyy_models.get("tts_voice", settings_obj.oxyy_tts_voice))
        settings_obj.oxyy_stt_model = str(oxyy_models.get("stt", settings_obj.oxyy_stt_model))
        settings_obj.oxyy_image_model = str(oxyy_models.get("image", settings_obj.oxyy_image_model))
        settings_obj.oxyy_video_model = str(oxyy_models.get("video", settings_obj.oxyy_video_model))
        settings_obj.oxyy_embedding_model = str(oxyy_models.get("embedding", settings_obj.oxyy_embedding_model))


# ---------------------------------------------------------------------------
# Perfil do agente (nome, estilo e frase de ativação)
# ---------------------------------------------------------------------------
# O perfil muda só a identidade apresentada no prompt e a frase do detector
# de voz. Permissões, ferramentas e aprovações não leem estes campos.
DEFAULT_AGENT_NAME = "Assistente"
DEFAULT_AGENT_STYLE = (
    "Neutro, cordial e conciso. Responda em português do Brasil, com frases curtas e diretas. "
    "Trate o usuário pelo nome quando souber, sem títulos ou apelidos."
)
_AGENT_NAME_MAX = 40
_AGENT_STYLE_MAX = 2000
_WAKE_PHRASE_MAX = 60
_WAKE_PHRASE_MAX_WORDS = 4


def _clean_agent_name(value: Any) -> str:
    name = " ".join(str(value or "").split())
    if not name:
        raise ValueError("Informe um nome para o agente.")
    if len(name) > _AGENT_NAME_MAX:
        raise ValueError(f"O nome do agente pode ter no máximo {_AGENT_NAME_MAX} caracteres.")
    return name


def _clean_agent_style(value: Any) -> str:
    style = str(value or "").strip()
    if len(style) > _AGENT_STYLE_MAX:
        raise ValueError(f"As instruções de estilo podem ter no máximo {_AGENT_STYLE_MAX} caracteres.")
    return style


def normalize_wake_phrase(value: Any) -> str:
    """Normaliza a frase de ativação: minúsculas, só letras e espaços simples."""
    phrase = " ".join(str(value or "").lower().split())
    if not phrase:
        return ""
    if len(phrase) > _WAKE_PHRASE_MAX:
        raise ValueError(f"A frase de ativação pode ter no máximo {_WAKE_PHRASE_MAX} caracteres.")
    if not all(ch.isalpha() or ch == " " for ch in phrase):
        raise ValueError("A frase de ativação aceita só letras e espaços, sem números ou pontuação.")
    if len(phrase.split()) > _WAKE_PHRASE_MAX_WORDS:
        raise ValueError(f"A frase de ativação pode ter no máximo {_WAKE_PHRASE_MAX_WORDS} palavras.")
    return phrase


def derive_wake_phrase(name: str) -> str:
    """Frase padrão derivada do nome: 'ei <nome>'."""
    try:
        return normalize_wake_phrase(f"ei {name}")
    except ValueError as exc:
        raise ValueError(
            f"Não foi possível derivar a frase de ativação do nome '{name}'. "
            "Informe uma frase de ativação só com letras e espaços."
        ) from exc


def _build_agent_profile(name: str, style: str, wake_phrase: str) -> dict[str, Any]:
    custom = bool(wake_phrase)
    return {
        "name": name,
        "style": style or DEFAULT_AGENT_STYLE,
        "wake_phrase": wake_phrase or derive_wake_phrase(name),
        "wake_phrase_custom": custom,
    }


def default_agent_profile() -> dict[str, Any]:
    return _build_agent_profile(DEFAULT_AGENT_NAME, DEFAULT_AGENT_STYLE, "")


def prepare_agent_profile(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida e normaliza um perfil recebido, sem gravar."""
    if not isinstance(payload, dict):
        raise ValueError("O perfil do agente deve ser um objeto.")
    name = _clean_agent_name(payload.get("name"))
    style = _clean_agent_style(payload.get("style"))
    wake_phrase = normalize_wake_phrase(payload.get("wake_phrase"))
    return _build_agent_profile(name, style, wake_phrase)


def get_agent_profile() -> dict[str, Any]:
    """Perfil ativo. Dados ausentes ou inválidos voltam ao perfil neutro."""
    saved = _read().get("agent_profile")
    if not isinstance(saved, dict):
        return default_agent_profile()
    try:
        return prepare_agent_profile(saved)
    except ValueError:
        return default_agent_profile()


def set_agent_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = prepare_agent_profile(payload)
    data = _read()
    data["agent_profile"] = {
        "name": profile["name"],
        "style": profile["style"],
        # Vazio significa "derivar do nome", para acompanhar trocas de nome.
        "wake_phrase": profile["wake_phrase"] if profile["wake_phrase_custom"] else "",
    }
    _write(data)
    return get_agent_profile()


def get_llm_provider(default: str | None = None) -> str:
    data = _read()
    if "llm_provider" in data:
        provider = str(data["llm_provider"]).lower()
        return provider if provider in _VALID_PROVIDERS else "gemini"
    env_provider = str(default if default is not None else os.getenv("LLM_PROVIDER", "gemini")).lower()
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
    provider = get_llm_provider(default_provider)
    routes = resolve_ai_routes({"llm_provider": default_provider})
    chat = routes["chat"]
    return {
        "llm_provider": provider,
        "gemini_configured": _configured("gemini"),
        "groq_configured": _configured("groq"),
        "oxyy_configured": _configured("oxyy"),
        "effective_provider": (chat.get("effective") or {}).get("provider"),
        "effective_model": (chat.get("effective") or {}).get("model"),
        "fallback_used": bool(chat.get("fallback_used")),
        "fallback_reason": chat.get("reason", ""),
        "route": chat,
    }


def get_oxyy_settings(defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Retorna escolhas por capacidade sem expor chaves secretas."""
    data = _read()
    merged = dict(_OXYY_MODEL_DEFAULTS)
    if defaults:
        for key, value in defaults.items():
            if value:
                merged[key] = value
    saved = data.get("oxyy_models")
    if isinstance(saved, dict):
        for key in merged:
            value = saved.get(key)
            if isinstance(value, str) and value.strip():
                merged[key] = value.strip()
    raw_keys = os.getenv("OXYY_API_KEYS", os.getenv("OXYY_API_KEY", ""))
    keys = [key.strip() for key in raw_keys.replace("\n", ",").split(",") if key.strip()]
    return {
        "models": merged,
        "oxyy_configured": bool(keys),
        "key_count": len(keys),
        "keys": [{"label": f"Chave {index + 1}", "masked": f"{key[:4]}…{key[-4:]}" if len(key) > 8 else "••••"} for index, key in enumerate(keys)],
        "base_url": os.getenv("OXYY_BASE_URL", "https://api.oxyy.ai/v1"),
    }


def set_oxyy_models(models: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(models, dict):
        raise ValueError("models deve ser um objeto.")
    data = _read()
    current = dict(data.get("oxyy_models") or {})
    allowed = set(_OXYY_MODEL_DEFAULTS)
    for key, value in models.items():
        if key not in allowed:
            continue
        value = str(value or "").strip()
        # Ignorar valores de placeholder do frontend tipo "official-chat"
        if not value or value.startswith("official-"):
            continue
        current[key] = value[:180]
    data["oxyy_models"] = current
    _write(data)
    return get_oxyy_settings()



def get_tts_provider(default: str = "fish") -> str:
    data = _read()
    if "tts_provider" in data:
        provider = str(data["tts_provider"]).lower()
        return provider if provider in _VALID_TTS_PROVIDERS else default
    env_provider = os.getenv("TTS_PROVIDER", default).lower()
    return env_provider if env_provider in _VALID_TTS_PROVIDERS else default


def set_tts_provider(provider: str) -> str:
    normalized = str(provider).lower()
    if normalized not in _VALID_TTS_PROVIDERS:
        raise ValueError(f"Provider TTS inválido: {provider}")
    data = _read()
    data["tts_provider"] = normalized
    _write(data)
    os.environ["TTS_PROVIDER"] = normalized
    return normalized


def get_tts_settings(default_provider: str = "fish") -> dict[str, Any]:
    provider = get_tts_provider(default_provider)
    return {
        "tts_provider": provider,
        "tts_voice": os.getenv("TTS_VOICE", "pt-BR-AntonioNeural"),
        "tts_gemini_voice": os.getenv("TTS_GEMINI_VOICE", "Charon"),
        "fish_reference_id": os.getenv("FISH_REFERENCE_ID", "78d40157e19a43ebb725f09fc6125585"),
        "fish_model": os.getenv("FISH_TTS_MODEL", "s2.1-pro-free"),
        "fish_configured": bool(os.getenv("FISH_API_KEY", "")),
        "gemini_configured": bool(os.getenv("GEMINI_API_KEY", "")),
        "oxyy_configured": bool(os.getenv("OXYY_API_KEY", "") or os.getenv("OXYY_API_KEYS", "")),
        "oxyy_model": os.getenv("OXYY_TTS_MODEL", "tts-1-hd"),
        "oxyy_voice": os.getenv("OXYY_TTS_VOICE", "alloy"),
    }


_TTS_VOICE_ENV = {"fish_reference_id": "FISH_REFERENCE_ID", "gemini": "TTS_GEMINI_VOICE", "edge": "TTS_VOICE"}


def set_tts_voices(values: dict[str, Any]) -> None:
    """Salva a voz escolhida dentro de cada provedor (fish_reference_id, gemini, edge)."""
    data = _read()
    current = dict(data.get("tts_voices")) if isinstance(data.get("tts_voices"), dict) else {}
    for key, env_name in _TTS_VOICE_ENV.items():
        if key in values:
            value = str(values[key] or "").strip()[:120]
            if value:
                current[key] = value
                os.environ[env_name] = value
    data["tts_voices"] = current
    _write(data)


def get_stt_provider(default: str = "groq") -> str:
    data = _read()
    value = data.get("stt_provider", os.getenv("STT_PROVIDER", default))
    value = str(value).lower()
    return value if value in _VALID_STT_PROVIDERS else default


def set_stt_provider(provider: str) -> str:
    normalized = str(provider).lower()
    if normalized not in _VALID_STT_PROVIDERS:
        raise ValueError(f"Provider STT inválido: {provider}")
    data = _read()
    data["stt_provider"] = normalized
    _write(data)
    os.environ["STT_PROVIDER"] = normalized
    return normalized


def get_stt_settings(default_provider: str = "groq") -> dict[str, Any]:
    from app.services.voice.stt import local_whisper

    available = local_whisper.is_available()
    model = local_whisper.configured_model()
    return {
        "stt_provider": get_stt_provider(default_provider),
        "groq_configured": bool(os.getenv("GROQ_API_KEY", "") or os.getenv("GROQ_API_KEYS", "")),
        "oxyy_configured": bool(os.getenv("OXYY_API_KEY", "") or os.getenv("OXYY_API_KEYS", "")),
        "oxyy_model": os.getenv("OXYY_STT_MODEL", "whisper-1"),
        "local_available": available,
        "local_reason": "" if available else local_whisper.unavailable_reason(),
        "local_model": model,
        "local_device": local_whisper.configured_device(),
        "local_model_downloaded": local_whisper.model_cached(model) if available else False,
        "local_models": list(local_whisper.VALID_MODELS),
        "local_download_hint": (
            "" if not available or local_whisper.model_cached(model)
            else f"O modelo '{model}' ({local_whisper.MODEL_SIZE_HINT.get(model, '')}) será baixado na primeira transcrição."
        ),
    }


def set_stt_local(model: str | None = None, device: str | None = None) -> dict[str, Any]:
    from app.services.voice.stt import local_whisper

    data = _read()
    if model is not None:
        model = str(model).lower()
        if model not in local_whisper.VALID_MODELS:
            raise ValueError(f"Modelo STT local inválido: {model}")
        data["stt_local_model"] = model
        os.environ["STT_LOCAL_MODEL"] = model
    if device is not None:
        device = str(device).lower()
        if device not in local_whisper.VALID_DEVICES:
            raise ValueError(f"Dispositivo STT local inválido: {device}")
        data["stt_local_device"] = device
        os.environ["STT_LOCAL_DEVICE"] = device
    _write(data)
    return get_stt_settings()


# Microfone: parametros do detector de fala (usados pelo navegador na ligacao e no ditado).
# Padroes baseados no Projeto AI (energy 1100, pausa 0.8s), um pouco mais sensiveis.
MIC_DEFAULTS: dict[str, Any] = {
    "sensitivity": 75,      # 1-100: quanto maior, mais facil detectar fala
    "silence_ms": 800,      # silencio para encerrar a fala (pause_threshold 0.8 do projeto antigo)
    "gain": 1.0,            # ganho aplicado ao nivel medido (0.5-4)
}
MIC_ENGINES = ("auto", "backend", "browser")  # auto = SpeechRecognition no PC quando possível
_MIC_LIMITS = {"sensitivity": (1, 100), "silence_ms": (300, 3000), "gain": (0.5, 4.0)}


def get_mic_settings() -> dict[str, Any]:
    saved = _read().get("mic")
    saved = saved if isinstance(saved, dict) else {}
    result: dict[str, Any] = {}
    for key, default in MIC_DEFAULTS.items():
        low, high = _MIC_LIMITS[key]
        try:
            value = float(saved.get(key, default))
        except (TypeError, ValueError):
            value = float(default)
        value = max(low, min(high, value))
        result[key] = round(value, 2) if key == "gain" else int(round(value))
    engine = str(saved.get("engine", "auto")).lower()
    result["engine"] = engine if engine in MIC_ENGINES else "auto"
    result["device_name"] = str(saved.get("device_name") or "")[:200]
    return result


def set_mic_settings(values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Configuração de microfone inválida.")
    data = _read()
    current = dict(data.get("mic")) if isinstance(data.get("mic"), dict) else {}
    for key in MIC_DEFAULTS:
        if key in values:
            try:
                float(values[key])
            except (TypeError, ValueError):
                raise ValueError(f"Valor inválido para {key}.")
            current[key] = values[key]
    if "engine" in values:
        engine = str(values["engine"]).lower()
        if engine not in MIC_ENGINES:
            raise ValueError("Motor de detecção inválido.")
        current["engine"] = engine
    if "device_name" in values:
        current["device_name"] = str(values["device_name"] or "")[:200]
    data["mic"] = current
    _write(data)
    return get_mic_settings()


# Loop agêntico (lote 6): quando o agente planeja, age, confere e continua sozinho.
AGENT_LOOP_MODES = ("auto", "always", "off")
AGENT_LOOP_DEFAULTS: dict[str, Any] = {"mode": "auto", "max_steps": 8, "max_model_calls": 10, "auto_verify": True, "extract_memory_always": False}
_AGENT_LOOP_LIMITS = {"max_steps": (1, 20), "max_model_calls": (1, 30)}
_AGENT_LOOP_LABELS = {"max_steps": "O limite de etapas", "max_model_calls": "O limite de chamadas ao modelo"}


def get_agent_loop_settings() -> dict[str, Any]:
    saved = _read().get("agent_loop")
    saved = saved if isinstance(saved, dict) else {}
    mode = str(saved.get("mode", AGENT_LOOP_DEFAULTS["mode"])).lower()
    result: dict[str, Any] = {"mode": mode if mode in AGENT_LOOP_MODES else "auto"}
    for key, (low, high) in _AGENT_LOOP_LIMITS.items():
        value = saved.get(key, AGENT_LOOP_DEFAULTS[key])
        result[key] = value if type(value) is int and low <= value <= high else AGENT_LOOP_DEFAULTS[key]
    verify = saved.get("auto_verify", True)
    result["auto_verify"] = verify if isinstance(verify, bool) else True
    extract_always = saved.get("extract_memory_always", False)
    result["extract_memory_always"] = extract_always if isinstance(extract_always, bool) else False
    return result


def set_agent_loop_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Valida tudo antes de gravar; valor inválido não altera nada."""
    if not isinstance(values, dict):
        raise ValueError("Configuração do agente inválida.")
    unknown = set(values) - set(AGENT_LOOP_DEFAULTS)
    if unknown:
        raise ValueError("Campo desconhecido na configuração do agente: " + ", ".join(sorted(unknown)) + ".")
    current = get_agent_loop_settings()
    if "mode" in values:
        mode = values["mode"]
        if not isinstance(mode, str) or mode.lower() not in AGENT_LOOP_MODES:
            raise ValueError("Modo do agente inválido: use auto, always ou off.")
        current["mode"] = mode.lower()
    for key, (low, high) in _AGENT_LOOP_LIMITS.items():
        if key in values:
            value = values[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{_AGENT_LOOP_LABELS[key]} deve ser um número inteiro de {low} a {high}.")
            current[key] = value
    if "auto_verify" in values:
        if not isinstance(values["auto_verify"], bool):
            raise ValueError("A verificação automática deve ser ligada ou desligada (true/false).")
        current["auto_verify"] = values["auto_verify"]
    if "extract_memory_always" in values:
        if not isinstance(values["extract_memory_always"], bool):
            raise ValueError("A extração de memórias de toda mensagem deve ser ligada ou desligada (true/false).")
        current["extract_memory_always"] = values["extract_memory_always"]
    data = _read()
    data["agent_loop"] = current
    _write(data)
    return get_agent_loop_settings()


# Popups do painel (lote 6): o agente mostra hábitos, agenda, água e anotações em cartões animados.
POPUP_DEFAULTS: dict[str, Any] = {"enabled": True, "auto": True, "ttl_seconds": 8, "max_visible": 1}
_POPUP_LIMITS = {"ttl_seconds": (0, 120), "max_visible": (1, 5)}
_POPUP_LABELS = {
    "enabled": "Mostrar popups", "auto": "Popups automáticos",
    "ttl_seconds": "O tempo para fechar sozinho", "max_visible": "O máximo de popups na tela",
}


def get_popup_settings() -> dict[str, Any]:
    saved = _read().get("popups")
    saved = saved if isinstance(saved, dict) else {}
    result: dict[str, Any] = {}
    for key in ("enabled", "auto"):
        value = saved.get(key, POPUP_DEFAULTS[key])
        result[key] = value if isinstance(value, bool) else POPUP_DEFAULTS[key]
    for key, (low, high) in _POPUP_LIMITS.items():
        value = saved.get(key, POPUP_DEFAULTS[key])
        result[key] = value if type(value) is int and low <= value <= high else POPUP_DEFAULTS[key]
    return result


def set_popup_settings(values: dict[str, Any]) -> dict[str, Any]:
    """Valida tudo antes de gravar; valor inválido não altera nada."""
    if not isinstance(values, dict):
        raise ValueError("Configuração dos popups inválida.")
    unknown = set(values) - set(POPUP_DEFAULTS)
    if unknown:
        raise ValueError("Campo desconhecido na configuração dos popups: " + ", ".join(sorted(unknown)) + ".")
    current = get_popup_settings()
    for key in ("enabled", "auto"):
        if key in values:
            if not isinstance(values[key], bool):
                raise ValueError(f"{_POPUP_LABELS[key]} deve ser ligado ou desligado (true/false).")
            current[key] = values[key]
    for key, (low, high) in _POPUP_LIMITS.items():
        if key in values:
            value = values[key]
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{_POPUP_LABELS[key]} deve ser um número inteiro de {low} a {high}.")
            current[key] = value
    data = _read()
    data["popups"] = current
    _write(data)
    return get_popup_settings()


# Notificações do Windows (Fase 3): notificações acionáveis com botões e deep links
NOTIFICATION_DEFAULTS: dict[str, Any] = {"enabled": True, "sound": True}


def get_notification_settings() -> dict[str, Any]:
    saved = _read().get("notifications")
    saved = saved if isinstance(saved, dict) else {}
    result: dict[str, Any] = {}
    for key in ("enabled", "sound"):
        value = saved.get(key, NOTIFICATION_DEFAULTS[key])
        result[key] = value if isinstance(value, bool) else NOTIFICATION_DEFAULTS[key]
    return result


def set_notification_settings(values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Configuração de notificações inválida.")
    unknown = set(values) - set(NOTIFICATION_DEFAULTS)
    if unknown:
        raise ValueError("Campo desconhecido na configuração de notificações: " + ", ".join(sorted(unknown)) + ".")
    current = get_notification_settings()
    for key in ("enabled", "sound"):
        if key in values:
            if not isinstance(values[key], bool):
                raise ValueError(f"O campo '{key}' deve ser booleano (true/false).")
            current[key] = values[key]
    data = _read()
    data["notifications"] = current
    _write(data)
    return get_notification_settings()



# Busca de lugares (lote 6): e-mail de contato opcional enviado ao Nominatim (política de uso do OSM).
def get_places_settings() -> dict[str, Any]:
    saved = _read().get("places")
    saved = saved if isinstance(saved, dict) else {}
    email = saved.get("email", "")
    valid = isinstance(email, str) and 3 <= len(email.strip()) <= 120 and "@" in email and " " not in email.strip()
    return {"email": email.strip() if valid else ""}


# Navegação Web Ativa (Playwright): modo headless vs visível e timeout defensivo.
BROWSER_SETTINGS_DEFAULTS: dict[str, Any] = {
    "headless": True,
    "timeout_seconds": 15,
}

def get_browser_settings() -> dict[str, Any]:
    saved = _read().get("browser")
    saved = saved if isinstance(saved, dict) else {}
    headless = saved.get("headless", BROWSER_SETTINGS_DEFAULTS["headless"])
    timeout_sec = saved.get("timeout_seconds", BROWSER_SETTINGS_DEFAULTS["timeout_seconds"])
    return {
        "headless": bool(headless) if isinstance(headless, bool) else True,
        "timeout_seconds": timeout_sec if isinstance(timeout_sec, int) and 1 <= timeout_sec <= 60 else 15,
    }

def set_browser_settings(values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Configuração do navegador inválida.")
    current = get_browser_settings()
    if "headless" in values:
        if not isinstance(values["headless"], bool):
            raise ValueError("O modo headless deve ser verdadeiro ou falso (true/false).")
        current["headless"] = values["headless"]
    if "timeout_seconds" in values:
        val = values["timeout_seconds"]
        if not isinstance(val, int) or not (1 <= val <= 60):
            raise ValueError("O tempo limite deve ser um número inteiro de 1 a 60 segundos.")
        current["timeout_seconds"] = val
    data = _read()
    data["browser"] = current
    _write(data)
    return get_browser_settings()


# ---------------------------------------------------------------------------
# Capability routes
# ---------------------------------------------------------------------------
# This is deliberately kept beside runtime_settings so every UI adapter and
# service reads the same effective route.  A catalog model never changes the
# selected provider by itself.
_CAPABILITIES = ("chat", "tts", "stt", "image", "video", "embedding")
MODEL_MODES = ("thinking", "planning", "research", "coder", "browser", "react", "lifeos", "tutor", "voice", "swarm")
_CAPABILITY_PROVIDERS = {
    "chat": ("gemini", "groq", "oxyy"),
    "tts": ("fish", "gemini", "edge", "oxyy"),
    "stt": ("groq", "google", "oxyy", "local"),
    "image": ("oxyy", "gemini"),
    "video": ("oxyy",),
    "embedding": ("oxyy", "gemini"),
}


def _keys_for(provider: str) -> list[str]:
    env_names = {
        "gemini": ("GEMINI_API_KEYS", "GEMINI_API_KEY"),
        "groq": ("GROQ_API_KEYS", "GROQ_API_KEY"),
        "oxyy": ("OXYY_API_KEYS", "OXYY_API_KEY"),
        "fish": ("FISH_API_KEYS", "FISH_API_KEY"),
        "google": ("GOOGLE_API_KEYS", "GOOGLE_API_KEY"),
    }
    for name in env_names.get(provider, ()):
        raw = os.getenv(name, "")
        if raw:
            return [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]
    return []


def _configured(provider: str) -> bool:
    # Edge is local and does not require an API key; all other remote routes
    # need credentials.  Google STT is intentionally marked unavailable when
    # no explicit key is present rather than pretending browser APIs are live.
    if provider == "local":
        from app.services.voice.stt import local_whisper
        return local_whisper.is_available()
    return provider == "edge" or bool(_keys_for(provider))


def _model_for(capability: str, provider: str, defaults: dict[str, Any] | None = None) -> str:
    defaults = defaults or {}
    oxyy = get_oxyy_settings(defaults.get("oxyy_models") if isinstance(defaults.get("oxyy_models"), dict) else None).get("models", {})
    env = {
        ("chat", "gemini"): os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash")),
        ("chat", "groq"): os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        ("chat", "oxyy"): oxyy.get("chat", "gemini-2.5-flash"),
        ("tts", "fish"): os.getenv("FISH_TTS_MODEL", "s2.1-pro-free"),
        ("tts", "gemini"): os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
        ("tts", "edge"): "edge-tts",
        ("tts", "oxyy"): oxyy.get("tts", "tts-1-hd"),
        ("stt", "local"): "faster-whisper " + os.getenv("STT_LOCAL_MODEL", "base"),
        ("stt", "groq"): os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
        ("stt", "oxyy"): oxyy.get("stt", "whisper-1"),
        ("stt", "google"): os.getenv("GOOGLE_STT_MODEL", "google-speech"),
        ("image", "oxyy"): oxyy.get("image", "dall-e-3"),
        ("image", "gemini"): os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.0-flash-exp"),
        ("video", "oxyy"): oxyy.get("video", "veo-3"),
        ("embedding", "oxyy"): oxyy.get("embedding", "gemini-embedding-001"),
        ("embedding", "gemini"): os.getenv("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
    }
    _SAFE_DEFAULTS = {
        ("chat", "oxyy"): "gpt-4o-mini",
        ("chat", "gemini"): "gemini-2.5-flash",
        ("chat", "groq"): "llama-3.3-70b-versatile",
        ("tts", "oxyy"): "tts-1-hd",
        ("stt", "oxyy"): "whisper-1",
        ("image", "oxyy"): "dall-e-3",
        ("video", "oxyy"): "veo-3",
        ("embedding", "oxyy"): "gemini-embedding-001",
    }
    result = str(env.get((capability, provider), defaults.get("model", "unknown")))
    # Sanitizar valores de placeholder (ex: "official-chat") que podem ter sido salvos por bug anterior
    if not result or result.startswith("official-") or result.startswith("the provider"):
        result = _SAFE_DEFAULTS.get((capability, provider), "gpt-4o-mini")
    return result


def _route(capability: str, primary_provider: str, *, primary_model: str | None = None) -> dict[str, Any]:
    providers = _CAPABILITY_PROVIDERS[capability]
    if primary_provider not in providers:
        primary_provider = providers[0]
    # Descartar modelos de placeholder salvos por bug anterior
    if primary_model and (primary_model.startswith("official-") or primary_model.startswith("the provider")):
        primary_model = None
    primary = {"provider": primary_provider, "model": primary_model or _model_for(capability, primary_provider)}
    fallback: list[dict[str, Any]] = []
    for provider in providers:
        if provider == primary_provider:
            continue
        fallback.append({
            "provider": provider,
            "model": _model_for(capability, provider),
            "configured": _configured(provider),
        })
    primary_configured = _configured(primary_provider)
    effective = primary if primary_configured else next((item for item in fallback if item["configured"]), None)
    if primary_configured:
        reason = "Rota principal configurada."
    else:
        missing = "faster-whisper não instalado (pip install faster-whisper)" if primary_provider == "local" else "sem chave/configuração"
        if effective:
            reason = f"{primary_provider}: {missing}; fallback efetivo em {effective['provider']}."
        else:
            reason = f"{primary_provider}: {missing} e nenhum fallback disponível."
    return {
        "capability": capability,
        "primary": primary,
        "primary_configured": primary_configured,
        "effective": effective,
        "fallback": fallback,
        "fallback_used": bool(effective and effective["provider"] != primary_provider),
        "reason": reason,
        "configured": bool(effective),
    }


def resolve_ai_routes(defaults: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    defaults = defaults or {}
    data = _read()
    saved = data.get("routes") if isinstance(data.get("routes"), dict) else {}
    providers = {
        "chat": get_llm_provider(str(defaults.get("llm_provider", os.getenv("LLM_PROVIDER", "gemini")))),
        "tts": get_tts_provider(str(defaults.get("tts_provider", os.getenv("TTS_PROVIDER", "fish")))),
        "stt": get_stt_provider(str(defaults.get("stt_provider", os.getenv("STT_PROVIDER", "groq")))),
        "image": str(saved.get("image", {}).get("provider", os.getenv("IMAGE_PROVIDER", "oxyy"))).lower(),
        "video": str(saved.get("video", {}).get("provider", os.getenv("VIDEO_PROVIDER", "oxyy"))).lower(),
        "embedding": str(saved.get("embedding", {}).get("provider", os.getenv("EMBEDDING_PROVIDER", "oxyy"))).lower(),
    }
    routes: dict[str, dict[str, Any]] = {}
    for capability in _CAPABILITIES:
        saved_route = saved.get(capability) if isinstance(saved.get(capability), dict) else {}
        provider = str(saved_route.get("provider", providers[capability])).lower()
        model = saved_route.get("model")
        routes[capability] = _route(capability, provider, primary_model=str(model) if model else None)
    for mode in MODEL_MODES:
        entry = saved.get(mode)
        if isinstance(entry, dict) and entry.get("provider"):
            routes[mode] = {**_route("chat", entry["provider"], primary_model=entry.get("model")), "capability": mode, "inherited": False}
        else:
            routes[mode] = {**routes["chat"], "capability": mode, "inherited": True}
    return routes


def get_ai_settings(defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    routes = resolve_ai_routes(defaults)
    return {"ok": True, "routes": routes, "effective": {key: value.get("effective") for key, value in routes.items()}}


def set_ai_routes(routes: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(routes, dict):
        raise ValueError("routes deve ser um objeto.")
    data = _read()
    current = data.get("routes") if isinstance(data.get("routes"), dict) else {}
    for capability, value in routes.items():
        if capability not in (*_CAPABILITIES, *MODEL_MODES) or not isinstance(value, dict):
            continue
        if capability in MODEL_MODES and value.get("inherit") is True:
            current.pop(capability, None)
            continue
        provider = str(value.get("provider", "")).lower()
        if provider not in _CAPABILITY_PROVIDERS["chat" if capability in MODEL_MODES else capability]:
            raise ValueError(f"Provider inválido para {capability}: {provider}")
        entry = {"provider": provider}
        if value.get("model"):
            entry["model"] = str(value["model"])[:180]
        current[capability] = entry
        if capability == "chat":
            data["llm_provider"] = provider
            os.environ["LLM_PROVIDER"] = provider
        elif capability == "tts":
            data["tts_provider"] = provider
            os.environ["TTS_PROVIDER"] = provider
        elif capability == "stt":
            data["stt_provider"] = provider
            os.environ["STT_PROVIDER"] = provider
    data["routes"] = current
    _write(data)
    return get_ai_settings()


# Monitor de eventos e alertas de recursos (Fase 3)
EVENT_SETTINGS_DEFAULTS: dict[str, Any] = {
    "enabled": True,
    "interval_seconds": 15,
    "cpu": {"enabled": False, "threshold": 90, "for_seconds": 120},
    "ram": {"enabled": False, "threshold": 90, "for_seconds": 120},
    "disk": {"enabled": False, "threshold": 95, "for_seconds": 120},
    "disk_path": "C:\\",
    "cooldown_minutes": 30,
}


def get_event_settings() -> dict[str, Any]:
    saved = _read().get("events")
    saved = saved if isinstance(saved, dict) else {}
    enabled = saved.get("enabled", EVENT_SETTINGS_DEFAULTS["enabled"])
    interval = saved.get("interval_seconds", EVENT_SETTINGS_DEFAULTS["interval_seconds"])
    cooldown = saved.get("cooldown_minutes", EVENT_SETTINGS_DEFAULTS["cooldown_minutes"])
    disk_path = saved.get("disk_path", EVENT_SETTINGS_DEFAULTS["disk_path"])

    result: dict[str, Any] = {
        "enabled": enabled if isinstance(enabled, bool) else True,
        "interval_seconds": interval if type(interval) is int and 10 <= interval <= 120 else 15,
        "cooldown_minutes": cooldown if type(cooldown) is int and 1 <= cooldown <= 1440 else 30,
        "disk_path": str(disk_path or "C:\\"),
    }

    for res in ("cpu", "ram", "disk"):
        default_res = EVENT_SETTINGS_DEFAULTS[res]
        val = saved.get(res)
        val = val if isinstance(val, dict) else {}
        r_enabled = val.get("enabled", default_res["enabled"])
        r_thresh = val.get("threshold", default_res["threshold"])
        r_for_sec = val.get("for_seconds", default_res["for_seconds"])
        result[res] = {
            "enabled": r_enabled if isinstance(r_enabled, bool) else default_res["enabled"],
            "threshold": r_thresh if type(r_thresh) is int and 50 <= r_thresh <= 99 else default_res["threshold"],
            "for_seconds": r_for_sec if type(r_for_sec) is int and 0 <= r_for_sec <= 3600 else default_res["for_seconds"],
        }
    return result


def set_event_settings(values: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(values, dict):
        raise ValueError("Configurações de eventos inválidas.")
    unknown = set(values) - set(EVENT_SETTINGS_DEFAULTS)
    if unknown:
        raise ValueError("Campo desconhecido na configuração de eventos: " + ", ".join(sorted(unknown)) + ".")

    current = get_event_settings()
    if "enabled" in values:
        if not isinstance(values["enabled"], bool):
            raise ValueError("O monitor de eventos deve ser ligado ou desligado (true/false).")
        current["enabled"] = values["enabled"]

    if "interval_seconds" in values:
        val = values["interval_seconds"]
        if type(val) is not int or not 10 <= val <= 120:
            raise ValueError("O intervalo de verificação deve ser um número inteiro de 10 a 120 segundos.")
        current["interval_seconds"] = val

    if "cooldown_minutes" in values:
        val = values["cooldown_minutes"]
        if type(val) is not int or not 1 <= val <= 1440:
            raise ValueError("O intervalo entre alertas deve ser um número inteiro de 1 a 1440 minutos.")
        current["cooldown_minutes"] = val

    if "disk_path" in values:
        path = values["disk_path"]
        if not isinstance(path, str) or not path.strip():
            raise ValueError("O caminho do disco deve ser um texto válido.")
        current["disk_path"] = path.strip()

    for res in ("cpu", "ram", "disk"):
        if res in values:
            val = values[res]
            if not isinstance(val, dict):
                raise ValueError(f"A configuração de {res.upper()} deve ser um objeto.")
            res_unknown = set(val) - {"enabled", "threshold", "for_seconds"}
            if res_unknown:
                raise ValueError(f"Campo desconhecido em {res.upper()}: " + ", ".join(sorted(res_unknown)) + ".")
            target_res = dict(current[res])
            if "enabled" in val:
                if not isinstance(val["enabled"], bool):
                    raise ValueError(f"O alerta de {res.upper()} deve ser ligado ou desligado (true/false).")
                target_res["enabled"] = val["enabled"]
            if "threshold" in val:
                t = val["threshold"]
                if type(t) is not int or not 50 <= t <= 99:
                    raise ValueError(f"O limiar de {res.upper()} deve ser um número inteiro de 50 a 99 %.")
                target_res["threshold"] = t
            if "for_seconds" in val:
                s = val["for_seconds"]
                if type(s) is not int or not 0 <= s <= 3600:
                    raise ValueError(f"A duração de {res.upper()} deve ser um número inteiro de 0 a 3600 segundos.")
                target_res["for_seconds"] = s
            current[res] = target_res

    data = _read()
    data["events"] = current
    _write(data)

    try:
        from app.routines.service import routine_service
        if hasattr(routine_service, "watcher") and routine_service.watcher is not None:
            routine_service.watcher.reload()
    except Exception:
        pass

    return get_event_settings()

