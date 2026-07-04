from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(slots=True)
class Settings:
    app_name: str = "Jarvis Rebuild"
    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = True
    data_dir: str = "data"


def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "Jarvis Rebuild"),
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=int(os.getenv("APP_PORT", "8000")),
        debug=os.getenv("APP_DEBUG", "1").lower() in {"1", "true", "yes"},
        data_dir=os.getenv("APP_DATA_DIR", "data"),
    )
