"""Motor primário de síntese de voz (TTS) — arquitetura multi-provider."""
from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Callable

from .cleaner import strip_text_for_speech
from .cache import TTSCache
from .prefetch import split_text_for_tts
from .providers.base import TTSProvider
from ..audio_io import AudioIO


class TTSEngine:
    """
    Orquestra a síntese de voz usando uma lista ordenada de providers.
    Tenta o primeiro; em caso de falha, cai automaticamente para o próximo.

    Ordem padrão: GeminiTTS → EdgeTTS → pyttsx3 (local)
    """

    def __init__(
        self,
        providers: list[TTSProvider] | None = None,
        # Parâmetros legados mantidos para compatibilidade
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "-5%",
        volume: str = "+0%",
        local_fallback: bool = True,
        cache_dir: str | Path = "data/tts_cache",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.local_fallback = local_fallback
        self.cache = TTSCache(cache_dir=cache_dir)
        self._providers: list[TTSProvider] = providers or []

    def add_provider(self, provider: TTSProvider) -> None:
        self._providers.append(provider)

    def speak(
        self,
        text: str,
        block: bool = True,
        on_start: Callable[[], None] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> str | None:
        """Sintetiza e reproduz o texto. Retorna o caminho do áudio gerado."""
        clean_text = strip_text_for_speech(text)
        if not clean_text:
            return None

        # Obtém o nome do provider ativo para o cache
        active_provider_name = self._active_provider_name()

        # Tenta cache global (texto completo)
        cached = self.cache.get_cached_file(clean_text, self.voice, provider=active_provider_name)
        if cached and cached.exists():
            if on_start:
                on_start()
            AudioIO.play_file(cached, block=block)
            if on_complete:
                on_complete()
            return str(cached)

        # Divide em blocos para textos longos
        chunks = split_text_for_tts(clean_text, max_chars=1500)
        generated_files: list[str] = []

        if on_start:
            on_start()

        for chunk in chunks:
            chunk_cached = self.cache.get_cached_file(chunk, self.voice, provider=active_provider_name)
            if chunk_cached and chunk_cached.exists():
                AudioIO.play_file(chunk_cached, block=block)
                generated_files.append(str(chunk_cached))
                continue

            audio_bytes, used_provider = self._generate_with_fallback(chunk)

            if audio_bytes:
                # Salva no cache
                ext = ".wav" if audio_bytes[:4] == b"RIFF" else ".mp3"
                tmp = tempfile.NamedTemporaryFile(
                    suffix=ext, prefix="jarvis_tts_", delete=False
                )
                tmp.write(audio_bytes)
                tmp.close()

                try:
                    self.cache.save_to_cache(
                        chunk, self.voice, tmp.name, provider=used_provider
                    )
                except Exception:
                    pass

                try:
                    AudioIO.play_file(tmp.name, block=block)
                    generated_files.append(tmp.name)
                except Exception as e:
                    print(f"[TTSEngine] Erro ao reproduzir áudio: {e}")
                    try:
                        os.unlink(tmp.name)
                    except OSError:
                        pass

            else:
                # Último recurso: pyttsx3 local
                if self.local_fallback:
                    tmp_wav = tempfile.mktemp(suffix=".wav", prefix="jarvis_tts_local_")
                    if self._speak_local(chunk, tmp_wav):
                        AudioIO.play_file(tmp_wav, block=block)
                        generated_files.append(tmp_wav)

        if on_complete:
            on_complete()

        return generated_files[0] if generated_files else None

    def _active_provider_name(self) -> str:
        """Nome do primeiro provider disponível (para chave de cache)."""
        for p in self._providers:
            if p.is_available():
                return p.name
        return "local"

    def _generate_with_fallback(self, text: str) -> tuple[bytes | None, str]:
        """
        Tenta cada provider em sequência.
        Retorna (audio_bytes, provider_name) ou (None, '').
        """
        for provider in self._providers:
            if not provider.is_available():
                continue
            try:
                audio = provider.generate(text)
                if audio:
                    return audio, provider.name
            except Exception as e:
                print(f"[TTSEngine] Provider '{provider.name}' falhou: {e}")
        return None, ""

    def _speak_local(self, text: str, output_path: str) -> bool:
        """Fallback local usando pyttsx3."""
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", 185)

            voices = engine.getProperty("voices")
            for v in voices:
                vid = getattr(v, "id", "").lower()
                vname = getattr(v, "name", "").lower()
                if "pt" in vid or "portuguese" in vname or "antonio" in vname:
                    engine.setProperty("voice", v.id)
                    break

            engine.save_to_file(text, output_path)
            engine.runAndWait()
            return os.path.exists(output_path) and os.path.getsize(output_path) > 0
        except Exception as e:
            print(f"[TTSEngine] Falha pyttsx3: {e}")
            return False

    def stop(self) -> None:
        AudioIO.stop()
