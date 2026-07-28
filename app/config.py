from __future__ import annotations

from dataclasses import dataclass, field
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env se ele existir
load_dotenv()

@dataclass(slots=True)
class Settings:
    app_name: str = "Jarvis Rebuild"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    data_dir: str = "data"
    
    # Chaves de API
    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_api_keys: list[str] = field(default_factory=list)
    groq_api_keys: list[str] = field(default_factory=list)
    
    # Configurações de IA e Voz
    llm_provider: str = "gemini"
    llm_model: str = "gemini-2.5-flash"
    groq_model: str = "llama-3.3-70b-versatile"
    tts_voice: str = "pt-BR-AntonioNeural"
    tts_provider: str = "gemini"          # gemini | edge | auto
    tts_gemini_voice: str = "Charon"       # Charon, Fenrir, Puck, Aoede, Kore, Zephyr
    stt_language: str = "pt-BR"


def load_settings() -> Settings:
    gem_raw = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    groq_raw = os.getenv("GROQ_API_KEYS", os.getenv("GROQ_API_KEY", ""))

    gem_keys = [k.strip() for k in gem_raw.replace("\n", ",").split(",") if k.strip()]
    groq_keys = [k.strip() for k in groq_raw.replace("\n", ",").split(",") if k.strip()]

    return Settings(
        app_name=os.getenv("APP_NAME", "Jarvis Rebuild"),
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        debug=os.getenv("APP_DEBUG", "1").lower() in {"1", "true", "yes"},
        data_dir=os.getenv("APP_DATA_DIR", "data"),
        gemini_api_key=gem_keys[0] if gem_keys else "",
        groq_api_key=groq_keys[0] if groq_keys else "",
        gemini_api_keys=gem_keys,
        groq_api_keys=groq_keys,
        llm_provider=os.getenv("LLM_PROVIDER", "gemini"),
        llm_model=os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-flash-latest")),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        tts_voice=os.getenv("TTS_VOICE", "pt-BR-AntonioNeural"),
        tts_provider=os.getenv("TTS_PROVIDER", "gemini"),
        tts_gemini_voice=os.getenv("TTS_GEMINI_VOICE", "Charon"),
        stt_language=os.getenv("STT_LANGUAGE", "pt-BR"),
    )
