from __future__ import annotations

from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env se ele existir
load_dotenv()

@dataclass(slots=True)
class Settings:
    app_name: str = "Jarvis"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    data_dir: str = "data"
    
    # Chaves de API
    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_keys: list[str] = field(default_factory=list)
    groq_api_keys: list[str] = field(default_factory=list)
    oxyy_api_key: str = ""
    oxyy_api_keys: list[str] = field(default_factory=list)
    oxyy_base_url: str = "https://api.oxyy.ai/v1"
    oxyy_model: str = "gpt-4o-mini"
    oxyy_chat_model: str = "gpt-4o-mini"
    oxyy_tts_model: str = "tts-1-hd"
    oxyy_tts_voice: str = "alloy"
    oxyy_stt_model: str = "whisper-1"
    oxyy_image_model: str = "dall-e-3"
    oxyy_video_model: str = "veo-3"
    oxyy_embedding_model: str = "gemini-embedding-001"
    
    # Configurações de IA e Voz
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    tts_voice: str = "pt-BR-AntonioNeural"
    tts_provider: str = "fish"            # fish | gemini | edge | oxyy | auto
    tts_gemini_voice: str = "Charon"       # Charon, Fenrir, Puck, Aoede, Kore, Zephyr
    fish_api_key: str = ""
    fish_reference_id: str = "78d40157e19a43ebb725f09fc6125585"
    fish_tts_model: str = "s2.1-pro-free"
    fish_auto_emotions: bool = True
    stt_language: str = "pt-BR"
    stt_provider: str = "groq"
    # Local control-plane boundary. LAN is opt-in and its secret never leaves
    # process memory through an API response.
    access_mode: str = "loopback"
    lan_enabled: bool = False
    control_token: str = ""
    trusted_origins: list[str] = field(default_factory=list)

    def validate_control_plane(self) -> None:
        if self.access_mode not in {"loopback", "lan"}:
            raise ValueError("APP_ACCESS_MODE must be 'loopback' or 'lan'.")
        if self.access_mode == "lan":
            if not self.lan_enabled:
                raise ValueError("LAN mode requires APP_LAN_ENABLED=1.")
            if not self.control_token:
                raise ValueError("LAN mode requires JARVIS_CONTROL_TOKEN. Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\"")
            if not self.trusted_origins:
                raise ValueError("LAN mode requires APP_TRUSTED_ORIGINS.")

    def public_control_plane_config(self) -> dict[str, object]:
        return {
            "access_mode": self.access_mode,
            "lan_enabled": self.lan_enabled,
            "trusted_origins": list(self.trusted_origins),
            "token_configured": bool(self.control_token),
        }


def load_settings() -> Settings:
    gem_raw = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    groq_raw = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))
    oxyy_raw = os.getenv("OXYY_API_KEYS", os.getenv("OXYY_API_KEY", ""))

    gem_keys = [k.strip() for k in gem_raw.replace("\n", ",").split(",") if k.strip()]
    groq_keys = [k.strip() for k in groq_raw.replace("\n", ",").split(",") if k.strip()]
    oxyy_keys = [k.strip() for k in oxyy_raw.replace("\n", ",").split(",") if k.strip()]
    origins_raw = os.getenv("APP_TRUSTED_ORIGINS", "")
    trusted_origins = [item.strip().rstrip("/") for item in origins_raw.split(",") if item.strip()]

    settings = Settings(
        app_name=os.getenv("APP_NAME", "Jarvis"),
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        debug=os.getenv("APP_DEBUG", "1").lower() in {"1", "true", "yes"},
        data_dir=os.getenv("APP_DATA_DIR", "data"),
        gemini_api_key=gem_keys[0] if gem_keys else "",
        groq_api_key=groq_keys[0] if groq_keys else "",
        gemini_api_keys=gem_keys,
        groq_api_keys=groq_keys,
        oxyy_api_key=oxyy_keys[0] if oxyy_keys else "",
        oxyy_api_keys=oxyy_keys,
        oxyy_base_url=os.getenv("OXYY_BASE_URL", "https://api.oxyy.ai/v1"),
        oxyy_model=os.getenv("OXYY_MODEL", "gpt-4o-mini"),
        oxyy_chat_model=os.getenv("OXYY_CHAT_MODEL", os.getenv("OXYY_MODEL", "gpt-4o-mini")),
        oxyy_tts_model=os.getenv("OXYY_TTS_MODEL", "tts-1-hd"),
        oxyy_tts_voice=os.getenv("OXYY_TTS_VOICE", "alloy"),
        oxyy_stt_model=os.getenv("OXYY_STT_MODEL", "whisper-1"),
        oxyy_image_model=os.getenv("OXYY_IMAGE_MODEL", "dall-e-3"),
        oxyy_video_model=os.getenv("OXYY_VIDEO_MODEL", "veo-3"),
        oxyy_embedding_model=os.getenv("OXYY_EMBEDDING_MODEL", "gemini-embedding-001"),
        llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
        llm_model=os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-flash-latest")),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        tts_voice=os.getenv("TTS_VOICE", "pt-BR-AntonioNeural"),
        tts_provider=os.getenv("TTS_PROVIDER", "fish"),
        tts_gemini_voice=os.getenv("TTS_GEMINI_VOICE", "Charon"),
        fish_api_key=os.getenv("FISH_API_KEY", ""),
        fish_reference_id=os.getenv("FISH_REFERENCE_ID", "78d40157e19a43ebb725f09fc6125585"),
        fish_tts_model=os.getenv("FISH_TTS_MODEL", "s2.1-pro-free"),
        fish_auto_emotions=os.getenv("FISH_AUTO_EMOTIONS", "1").lower() in {"1", "true", "yes", "on"},
        stt_language=os.getenv("STT_LANGUAGE", "pt-BR"),
        stt_provider=os.getenv("STT_PROVIDER", "groq"),
        access_mode=os.getenv("APP_ACCESS_MODE", "loopback").lower().strip(),
        lan_enabled=os.getenv("APP_LAN_ENABLED", "0").lower() in {"1", "true", "yes", "on"},
        control_token=os.getenv("JARVIS_CONTROL_TOKEN", ""),
        trusted_origins=trusted_origins,
    )
    # Preferências escolhidas no painel sobrevivem ao reinício do processo.
    # O bloco é opcional para manter a configuração importável em instalações
    # mínimas que ainda não criaram o diretório data/.
    try:
        from app.storage.runtime_settings import get_llm_provider, get_ai_settings, get_oxyy_settings, get_stt_provider, get_tts_provider
        settings.llm_provider = get_llm_provider(settings.llm_provider)
        settings.tts_provider = get_tts_provider(settings.tts_provider)
        settings.stt_provider = get_stt_provider(settings.stt_provider)
        selected = get_oxyy_settings({
            "chat": settings.oxyy_chat_model,
            "tts": settings.oxyy_tts_model,
            "tts_voice": settings.oxyy_tts_voice,
            "stt": settings.oxyy_stt_model,
            "image": settings.oxyy_image_model,
            "video": settings.oxyy_video_model,
            "embedding": settings.oxyy_embedding_model,
        }).get("models", {})
        def _clean_model(val: str, fallback: str) -> str:
            """Descarta IDs de placeholder salvos por bug anterior (ex: 'official-chat')."""
            v = str(val or "").strip()
            if not v or v.startswith("official-") or v.startswith("the provider"):
                return fallback
            return v

        settings.oxyy_chat_model = _clean_model(selected.get("chat", settings.oxyy_chat_model), "gemini-2.5-flash")
        settings.oxyy_model = settings.oxyy_chat_model
        settings.oxyy_tts_model = _clean_model(selected.get("tts", settings.oxyy_tts_model), "tts-1-hd")
        settings.oxyy_tts_voice = _clean_model(selected.get("tts_voice", settings.oxyy_tts_voice), "alloy")
        settings.oxyy_stt_model = _clean_model(selected.get("stt", settings.oxyy_stt_model), "whisper-1")
        settings.oxyy_image_model = _clean_model(selected.get("image", settings.oxyy_image_model), "dall-e-3")
        settings.oxyy_video_model = _clean_model(selected.get("video", settings.oxyy_video_model), "veo-3")
        settings.oxyy_embedding_model = _clean_model(selected.get("embedding", settings.oxyy_embedding_model), "gemini-embedding-001")
        chat_route = get_ai_settings({
            "llm_provider": settings.llm_provider,
            "tts_provider": settings.tts_provider,
            "stt_provider": settings.stt_provider,
        }).get("routes", {}).get("chat", {})
        primary = chat_route.get("primary") or {}
        if primary.get("provider") == "gemini" and primary.get("model"):
            settings.llm_model = str(primary["model"])
        elif primary.get("provider") == "groq" and primary.get("model"):
            settings.groq_model = str(primary["model"])
    except Exception:
        pass
    return settings
