from __future__ import annotations

import json
import sys
from typing import Any

from app.storage.runtime_settings import (
    get_agent_profile,
    prepare_agent_profile,
    set_agent_profile,
    get_llm_settings,
    get_ai_settings,
    get_oxyy_settings,
    get_stt_settings,
    get_tts_settings,
    get_api_keys,
    set_api_keys,
    set_llm_provider,
    set_ai_routes,
    set_oxyy_models,
    set_stt_provider,
    set_stt_local,
    get_mic_settings,
    set_mic_settings,
    set_tts_provider,
    sync_api_keys_to_env,
    sync_settings_to_obj,
)


def _save_agent_profile(body: bytes) -> tuple[int, dict[str, Any]]:
    """Valida, confere a frase no vocabulário do detector local e grava o perfil.

    O perfil não toca em permissões, ferramentas nem aprovações: só o prompt e
    a frase de ativação leem estes campos.
    """
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
        profile = prepare_agent_profile(payload.get("profile", payload) if isinstance(payload, dict) else payload)
    except json.JSONDecodeError:
        return 400, {"ok": False, "error": "JSON inválido."}
    except ValueError as exc:
        return 400, {"ok": False, "error": str(exc)}
    from app.services.voice.wake_word import check_wake_phrase_vocabulary
    check = check_wake_phrase_vocabulary(profile["wake_phrase"])
    if check.get("supported") is False:
        return 400, {"ok": False, "error": check["message"], "wake_phrase_check": check}
    saved = set_agent_profile(profile if profile["wake_phrase_custom"] else {**profile, "wake_phrase": ""})
    _refresh_wake_detector(saved["wake_phrase"])
    return 200, {"ok": True, "profile": saved, "wake_phrase_check": check}


def _refresh_wake_detector(wake_phrase: str) -> None:
    """Atualiza o detector em execução, se houver, sem importar o servidor."""
    server = sys.modules.get("app.ui.panel.server")
    detector = getattr(server, "_wake_word_detector", None) if server else None
    if detector is not None and hasattr(detector, "set_wake_phrase"):
        detector.set_wake_phrase(wake_phrase)


def _sync_merge(body: bytes, handler: Any) -> tuple[int, dict[str, Any]]:
    """Mescla o snapshot vindo da nuvem com os dados locais e grava o resultado.

    A resposta traz o snapshot mesclado (inclui as chaves completas, para o
    cliente enviar de volta à nuvem) e só contagens no resumo.
    """
    from app.storage import backend_sync

    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return 400, {"ok": False, "error": "JSON inválido."}
    remote = payload.get("snapshot") if isinstance(payload, dict) else None
    if remote is not None and not isinstance(remote, dict):
        return 400, {"ok": False, "error": "snapshot deve ser um objeto."}
    try:
        merged, summary = backend_sync.sync_with_remote(remote or {})
    except Exception as exc:  # noqa: BLE001 - nenhuma exceção pode carregar valores sensíveis
        return 500, {"ok": False, "error": f"Falha ao mesclar dados: {type(exc).__name__}"}
    sync_api_keys_to_env()
    sync_settings_to_obj(handler.settings)
    _refresh_wake_detector(get_agent_profile()["wake_phrase"])
    return 200, {"ok": True, "snapshot": merged, "summary": summary}


def handle_settings_get(parts: list[str], handler: Any) -> tuple[int, dict[str, Any]] | None:
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "agent-profile":
        return 200, {"ok": True, "profile": get_agent_profile()}
    if len(parts) == 3 and parts[1] == "settings" and parts[2] == "sync-snapshot":
        from app.storage import backend_sync

        return 200, {"ok": True, "snapshot": backend_sync.collect_snapshot()}
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "keys":
        return 200, {"ok": True, "keys": get_api_keys()}
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "ai":
        defaults = {
            "llm_provider": getattr(handler.settings, "llm_provider", "gemini"),
            "tts_provider": getattr(handler.settings, "tts_provider", "fish"),
            "stt_provider": getattr(handler.settings, "stt_provider", "local"),
        }
        return 200, get_ai_settings(defaults)
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "llm":
        default = getattr(handler.settings, "llm_provider", "gemini")
        data = get_llm_settings(default)
        # Include provider-specific models for sync - use native provider models, not route proxy models
        # For Groq, always use the native Groq model name (llama-3.3-70b-versatile), not proxy names like openai/gpt-oss-120b
        provider = data.get("llm_provider", "gemini")
        if provider == "groq":
            # Use the native Groq model from settings, or the default
            groq_model = getattr(handler.settings, "groq_model", "llama-3.3-70b-versatile")
            # If the stored model is a proxy name (starts with openai/ or other prefixes), use the default native model
            if groq_model.startswith("openai/") or "/" in groq_model:
                groq_model = "llama-3.3-70b-versatile"
            data["groq_model"] = groq_model
        else:
            data["groq_model"] = getattr(handler.settings, "groq_model", "llama-3.3-70b-versatile")
        data["gemini_model"] = getattr(handler.settings, "llm_model", "gemini-flash-latest")
        data["oxyy_model"] = getattr(handler.settings, "oxyy_chat_model", getattr(handler.settings, "oxyy_model", "gemini-2.5-flash"))
        return 200, data
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "tts":
        default = getattr(handler.settings, "tts_provider", "fish")
        return 200, get_tts_settings(default)
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "mic":
        return 200, {"ok": True, **get_mic_settings()}
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "stt":
        default = getattr(handler.settings, "stt_provider", "local")
        return 200, get_stt_settings(default)
    if len(parts) >= 3 and parts[1] == "settings" and parts[2] == "oxyy":
        defaults = {
            "chat": getattr(handler.settings, "oxyy_chat_model", getattr(handler.settings, "oxyy_model", "gemini-2.5-flash")),
            "tts": getattr(handler.settings, "oxyy_tts_model", "tts-1-hd"),
            "tts_voice": getattr(handler.settings, "oxyy_tts_voice", "alloy"),
            "stt": getattr(handler.settings, "oxyy_stt_model", "whisper-1"),
            "image": getattr(handler.settings, "oxyy_image_model", "dall-e-3"),
            "video": getattr(handler.settings, "oxyy_video_model", "veo-3"),
            "embedding": getattr(handler.settings, "oxyy_embedding_model", "gemini-embedding-001"),
        }
        result = get_oxyy_settings(defaults)
        if parts[2] == "oxyy" and len(parts) >= 4 and parts[3] == "models":
            from app.services.oxyy import fetch_models, group_models
            keys = getattr(handler.settings, "oxyy_api_keys", []) or [getattr(handler.settings, "oxyy_api_key", "")]
            models, remote, error = [], False, None
            usable_keys = [key for key in keys if key]
            for key in usable_keys:
                models, remote, error = fetch_models(
                    key,
                    getattr(handler.settings, "oxyy_base_url", result.get("base_url", "")),
                )
                if remote:
                    break
            if not usable_keys:
                models, remote, error = fetch_models(
                    "",
                    getattr(handler.settings, "oxyy_base_url", result.get("base_url", "")),
                )
            return 200, {"ok": True, "models": group_models(models), "all": models, "remote": remote, "error": error}
        return 200, result
    return None


def handle_settings_post(path: str, body: bytes, handler: Any) -> tuple[int, dict[str, Any]] | None:
    if path in {"/api/settings/agent-profile", "/api/settings/agent-profile/"}:
        return _save_agent_profile(body)
    if path in {"/api/settings/sync-merge", "/api/settings/sync-merge/"}:
        return _sync_merge(body, handler)
    if path in {"/api/settings/keys", "/api/settings/keys/"}:
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            keys = payload.get("keys", payload)
            updated = set_api_keys(keys, handler.settings)
            return 200, {"ok": True, "keys": updated}
        except Exception as exc:
            return 400, {"ok": False, "error": str(exc)}
    if path == "/api/settings/llm":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return 400, {"ok": False, "error": "JSON inválido."}
        provider = payload.get("llm_provider")
        if not provider:
            return 400, {"ok": False, "error": "Campo llm_provider é obrigatório."}

        try:
            set_llm_provider(str(provider))
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}

        handler.settings.llm_provider = str(provider).lower()
        default = getattr(handler.settings, "llm_provider", "gemini")
        data = get_llm_settings(default)
        # Include provider-specific models for sync - use native provider models, not route proxy models
        # For Groq, always use the native Groq model name (llama-3.3-70b-versatile), not proxy names like openai/gpt-oss-120b
        if str(provider).lower() == "groq":
            # Use the native Groq model from settings, or the default
            groq_model = getattr(handler.settings, "groq_model", "llama-3.3-70b-versatile")
            # If the stored model is a proxy name (starts with openai/ or other prefixes), use the default native model
            if groq_model.startswith("openai/") or "/" in groq_model:
                groq_model = "llama-3.3-70b-versatile"
            data["groq_model"] = groq_model
        else:
            data["groq_model"] = getattr(handler.settings, "groq_model", "llama-3.3-70b-versatile")
        data["gemini_model"] = getattr(handler.settings, "llm_model", "gemini-flash-latest")
        data["oxyy_model"] = getattr(handler.settings, "oxyy_chat_model", getattr(handler.settings, "oxyy_model", "gemini-2.5-flash"))
        data["ok"] = True
        return 200, data

    if path in {"/api/settings/ai", "/api/settings/ai/"}:
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            routes = payload.get("routes", payload)
            result = set_ai_routes(routes)
            # Aplicar as três rotas com consumidores já existentes sem reinício.
            chat = result.get("routes", {}).get("chat", {}).get("primary", {})
            tts = result.get("routes", {}).get("tts", {}).get("primary", {})
            stt = result.get("routes", {}).get("stt", {}).get("primary", {})
            if chat.get("provider"):
                handler.settings.llm_provider = chat["provider"]
            if tts.get("provider"):
                handler.settings.tts_provider = tts["provider"]
            if stt.get("provider"):
                handler.settings.stt_provider = stt["provider"]
            # O agregado aplica as três rotas de voz de uma vez. Recriar o
            # pipeline uma única vez evita estado parcialmente atualizado.
            if tts.get("provider") or stt.get("provider"):
                try:
                    from app.services.voice.pipeline import VoicePipeline
                    handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)
                except Exception as exc:
                    print(f"[Settings] Falha ao recarregar pipeline após atualização de rotas: {exc}")
            result["ok"] = True
            return 200, result
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return 400, {"ok": False, "error": str(exc)}

    if path == "/api/settings/oxyy":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            models = payload.get("models", payload)
            result = set_oxyy_models(models)
            # A seleção feita no painel entra em vigor sem reiniciar o processo.
            settings = handler.settings
            mapping = {
                "chat": "oxyy_chat_model", "tts": "oxyy_tts_model", "tts_voice": "oxyy_tts_voice",
                "stt": "oxyy_stt_model", "image": "oxyy_image_model", "video": "oxyy_video_model",
                "embedding": "oxyy_embedding_model",
            }
            for key, attr in mapping.items():
                if key in result.get("models", {}):
                    setattr(settings, attr, result["models"][key])
            settings.oxyy_model = result["models"].get("chat", getattr(settings, "oxyy_model", "gemini-2.5-flash"))
            try:
                from app.services.voice.pipeline import VoicePipeline
                handler.__class__.voice_pipeline = VoicePipeline(settings=settings)
            except Exception as exc:
                print(f"[Settings] Falha ao recarregar modelos de voz Oxyy: {exc}")
            result["ok"] = True
            return 200, result
        except (ValueError, TypeError) as exc:
            return 400, {"ok": False, "error": str(exc)}

    if path == "/api/settings/tts":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            return 400, {"ok": False, "error": "JSON inválido."}

        provider = payload.get("tts_provider")
        voices = payload.get("voices") if isinstance(payload.get("voices"), dict) else {}
        if not provider and not voices:
            return 400, {"ok": False, "error": "Campo tts_provider é obrigatório."}

        try:
            if provider:
                set_tts_provider(str(provider))
            if voices:
                from app.storage.runtime_settings import set_tts_voices, sync_settings_to_obj
                set_tts_voices(voices)
                sync_settings_to_obj(handler.settings)
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}
        provider = provider or getattr(handler.settings, "tts_provider", "fish")

        # A troca feita no painel deve valer para a próxima fala sem exigir
        # reiniciar o servidor. O pipeline é pequeno e pode ser reconstruído
        # de forma segura entre duas requisições de voz.
        try:
            handler.settings.tts_provider = str(provider).lower()
            from app.services.voice.pipeline import VoicePipeline
            handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)
        except Exception as exc:
            print(f"[Settings] Falha ao recarregar TTS: {exc}")

        default = getattr(handler.settings, "tts_provider", "fish")
        data = get_tts_settings(default)
        data["ok"] = True
        return 200, data

    if path == "/api/settings/mic":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            return 200, {"ok": True, **set_mic_settings(payload)}
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}

    if path == "/api/settings/stt":
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            provider = payload.get("stt_provider")
            has_local = payload.get("local_model") or payload.get("local_device")
            if not provider and not has_local:
                return 400, {"ok": False, "error": "Informe stt_provider, local_model ou local_device."}
            if has_local:
                set_stt_local(payload.get("local_model"), payload.get("local_device"))
            if provider:
                set_stt_provider(str(provider))
                handler.settings.stt_provider = str(provider).lower()
            # A pipeline nova garante que a seleção seja aplicada à próxima fala.
            from app.services.voice.pipeline import VoicePipeline
            handler.__class__.voice_pipeline = VoicePipeline(settings=handler.settings)
            data = get_stt_settings(handler.settings.stt_provider)
            data["ok"] = True
            return 200, data
        except ValueError as exc:
            return 400, {"ok": False, "error": str(exc)}

    return None
