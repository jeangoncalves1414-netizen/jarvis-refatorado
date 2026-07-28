"""Provider Gemini TTS — usa Gemini 2.5 Flash para síntese de voz natural em PT-BR."""
from __future__ import annotations

import io
import os
import struct
import tempfile
import wave
from itertools import cycle
from typing import Iterator

from .base import TTSProvider

# Vozes disponíveis no Gemini TTS:
# Charon  → profunda, autoritária (melhor para JARVIS)
# Fenrir  → grave, séria
# Puck    → expressiva, animada
# Aoede   → feminina, suave
# Kore    → feminina, equilibrada
# Zephyr  → neutra, clara
JARVIS_VOICE = "Charon"


class GeminiTTSProvider(TTSProvider):
    """
    Sintetiza áudio com Gemini 2.5 Flash TTS.
    Suporta rotação automática de múltiplas chaves para maximizar quota.
    O Gemini detecta o idioma do texto automaticamente — texto em PT-BR = voz em PT-BR.
    """

    MODEL = "gemini-2.5-flash-preview-tts"

    def __init__(
        self,
        api_keys: list[str],
        voice: str = JARVIS_VOICE,
    ) -> None:
        self._voice = voice
        self._keys = [k for k in api_keys if k.strip()]
        self._key_cycle: Iterator[str] = cycle(self._keys) if self._keys else iter([])
        self._current_key: str = next(self._key_cycle) if self._keys else ""

    @property
    def name(self) -> str:
        return "gemini"

    def is_available(self) -> bool:
        return bool(self._keys)

    def _next_key(self) -> str:
        """Rotaciona para a próxima chave. Seguro mesmo com 1 chave (cycle repete)."""
        if not self._keys:
            return ""
        self._current_key = next(self._key_cycle)
        return self._current_key

    def generate(self, text: str) -> bytes | None:
        if not self._keys:
            print("[GeminiTTS] Nenhuma chave configurada.")
            return None

        # Tenta até N keys antes de desistir
        attempts = min(len(self._keys), 3)
        for attempt in range(attempts):
            try:
                audio_bytes = self._call_api(self._current_key, text)
                if audio_bytes:
                    return audio_bytes
                # Sem áudio = rotaciona chave e tenta novamente
                self._next_key()
            except Exception as e:
                err = str(e)
                print(f"[GeminiTTS] Erro (tentativa {attempt+1}/{attempts}): {err}")
                if "RESOURCE_EXHAUSTED" in err or "429" in err or "quota" in err.lower():
                    print(f"[GeminiTTS] Quota esgotada nessa chave. Rotacionando...")
                    self._next_key()
                else:
                    # Erro inesperado — não tenta novamente
                    break

        print("[GeminiTTS] Falha após todas as tentativas.")
        return None

    def _call_api(self, api_key: str, text: str) -> bytes | None:
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            print("[GeminiTTS] google-genai não instalado. Execute: pip install google-genai")
            return None

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=self.MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=self._voice,
                        )
                    )
                ),
            ),
        )

        # Gemini TTS retorna PCM raw (16-bit, 24kHz, mono) inline em base64
        part = response.candidates[0].content.parts[0]
        if not hasattr(part, "inline_data") or not part.inline_data:
            print("[GeminiTTS] Resposta sem dados de áudio.")
            return None

        pcm_bytes = part.inline_data.data
        if not pcm_bytes:
            return None

        # Converte PCM raw → WAV em memória (sem dependências extras)
        wav_bytes = _pcm_to_wav(pcm_bytes, sample_rate=24000, channels=1, sampwidth=2)
        return wav_bytes


def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 24000, channels: int = 1, sampwidth: int = 2) -> bytes:
    """Envolve PCM raw em container WAV para reprodução com qualquer player."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data)
    return buf.getvalue()
