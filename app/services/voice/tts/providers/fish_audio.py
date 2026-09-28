"""Provider Fish Audio TTS (S2.1 Pro).

The Fish API returns the encoded audio directly from ``/v1/tts``.  Keeping
this provider synchronous matches the existing TTS provider contract and
lets the engine keep its normal fallback/cache behaviour.
"""
from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .base import TTSProvider
from ..emotions import add_emotion_cues


class FishAudioProvider(TTSProvider):
    """Synthesize Portuguese speech with Fish Audio's S2.1 Pro model."""

    API_URL = "https://api.fish.audio/v1/tts"
    DEFAULT_MODEL = "s2.1-pro-free"
    DEFAULT_REFERENCE_ID = "78d40157e19a43ebb725f09fc6125585"

    def __init__(
        self,
        api_key: str | None = None,
        reference_id: str = DEFAULT_REFERENCE_ID,
        model: str = DEFAULT_MODEL,
        auto_emotions: bool = True,
        timeout: float = 30.0,
    ) -> None:
        # ``None`` means "read the environment"; an explicit empty string is
        # useful for tests and for deliberately disabling the provider.
        self._api_key = (os.getenv("FISH_API_KEY", "") if api_key is None else api_key).strip()
        self._reference_id = (reference_id or os.getenv("FISH_REFERENCE_ID", self.DEFAULT_REFERENCE_ID)).strip()
        self._model = (model or os.getenv("FISH_TTS_MODEL", self.DEFAULT_MODEL)).strip()
        self._auto_emotions = auto_emotions
        self._timeout = max(5.0, float(timeout))

    @property
    def name(self) -> str:
        return "fish"

    @property
    def reference_id(self) -> str:
        return self._reference_id

    def is_available(self) -> bool:
        return bool(self._api_key and self._reference_id)

    def generate(self, text: str) -> bytes | None:
        if not self.is_available():
            print("[FishTTS] FISH_API_KEY não configurada.")
            return None
        # S2 understands natural-language cues such as [warmly], [concerned]
        # and [laugh]. They are added only to the provider payload; the chat
        # and transcript continue to contain the original text.
        request = self._build_request(text)
        try:
            with urlopen(request, timeout=self._timeout) as response:
                audio = response.read()
            return audio or None
        except HTTPError as exc:
            self._log_http_error(exc)
        except (URLError, TimeoutError, OSError) as exc:
            print(f"[FishTTS] Falha de conexão: {exc}")
        except Exception as exc:
            print(f"[FishTTS] Erro inesperado: {exc}")
        return None

    def generate_stream(self, text: str):
        """Yield MP3 chunks as Fish generates them.

        This is intentionally Fish-only. If Fish is unavailable, the caller
        can use the normal endpoint and its Edge fallback instead of mixing
        providers inside one live response.
        """
        if not self.is_available():
            return None

        request = self._build_request(text)

        def chunks():
            response = None
            try:
                response = urlopen(request, timeout=self._timeout)
                while True:
                    chunk = response.read(8192)
                    if not chunk:
                        break
                    yield chunk
            except HTTPError as exc:
                self._log_http_error(exc)
            except (URLError, TimeoutError, OSError) as exc:
                print(f"[FishTTS] Falha de conexão no streaming: {exc}")
            except Exception as exc:
                print(f"[FishTTS] Erro inesperado no streaming: {exc}")
            finally:
                if response is not None:
                    response.close()

        return chunks()

    def _build_request(self, text: str) -> Request:
        speech_text = add_emotion_cues(text, enabled=self._auto_emotions, model=self._model)
        payload = json.dumps(
            {
                "text": speech_text,
                "reference_id": self._reference_id,
                "temperature": 0.7,
                "top_p": 0.7,
                "prosody": {"speed": 1.4, "volume": 0, "normalize_loudness": True},
                "latency": "normal",
                "chunk_length": 100,
                "min_chunk_length": 30,
                "condition_on_previous_chunks": True,
                "format": "mp3",
            },
            ensure_ascii=False,
        ).encode("utf-8")
        return Request(
            self.API_URL,
            data=payload,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
                "model": self._model,
            },
        )

    @staticmethod
    def _log_http_error(exc: HTTPError) -> None:
        detail = ""
        try:
            detail = exc.read(500).decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"[FishTTS] HTTP {exc.code}: {detail}")
