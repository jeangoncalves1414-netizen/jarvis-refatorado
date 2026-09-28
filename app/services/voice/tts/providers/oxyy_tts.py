"""Provider TTS do Oxyy (endpoint OpenAI-compatible /audio/speech)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import TTSProvider


class OxyyTTSProvider(TTSProvider):
    name = "oxyy"

    def __init__(self, api_keys: list[str] | None = None, model: str = "tts-1-hd", voice: str = "alloy", base_url: str = "https://api.oxyy.ai/v1") -> None:
        self.api_keys = [str(key).strip() for key in (api_keys or []) if str(key).strip()]
        self.model = model or "tts-1-hd"
        self.voice = voice or "alloy"
        self.base_url = (base_url or "https://api.oxyy.ai/v1").rstrip("/")

    def is_available(self) -> bool:
        return bool(self.api_keys)

    def generate(self, text: str) -> bytes | None:
        if not self.is_available() or not text.strip():
            return None
        payload = json.dumps({"model": self.model, "voice": self.voice, "input": text}).encode("utf-8")
        last_error: Exception | None = None
        for key in self.api_keys:
            request = urllib.request.Request(
                f"{self.base_url}/audio/speech",
                data=payload,
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "audio/mpeg"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    audio = response.read()
                if audio:
                    return audio
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc
        if last_error:
            raise last_error
        return None

    def generate_stream(self, text: str):
        """Entrega o corpo MP3 em blocos para o modo ligação de baixa latência."""
        if not self.is_available() or not text.strip():
            return None
        payload = json.dumps({"model": self.model, "voice": self.voice, "input": text}).encode("utf-8")

        def chunks():
            for key in self.api_keys:
                request = urllib.request.Request(
                    f"{self.base_url}/audio/speech",
                    data=payload,
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "audio/mpeg"},
                    method="POST",
                )
                response = None
                try:
                    response = urllib.request.urlopen(request, timeout=45)
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            return
                        yield chunk
                except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as exc:
                    print(f"[OxyyTTS] Streaming falhou ({exc}); tentando a próxima chave...")
                finally:
                    if response is not None:
                        response.close()

        return chunks()
