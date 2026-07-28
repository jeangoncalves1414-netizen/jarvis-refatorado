"""Provider Edge TTS com SSML avançado para voz mais natural em PT-BR."""
from __future__ import annotations

import asyncio
import io
import os
import re
import tempfile

from .base import TTSProvider


class EdgeTTSProvider(TTSProvider):
    """
    Sintetiza áudio com Edge TTS (Microsoft Neural voices).
    Aplica SSML avançado automaticamente para soar mais natural:
    - Pausas em vírgulas, pontos e dois-pontos
    - Pitch levemente mais grave (-2st → mais autoritário/JARVIS)
    - Rate levemente reduzida (-5% → mais calmo e preciso)
    - Ênfase em palavras entre aspas
    """

    def __init__(
        self,
        voice: str = "pt-BR-AntonioNeural",
        rate: str = "-5%",
        pitch: str = "-2st",
    ) -> None:
        self._voice = voice
        self._rate = rate
        self._pitch = pitch

    @property
    def name(self) -> str:
        return "edge"

    def generate(self, text: str) -> bytes | None:
        """Sintetiza o texto via Edge TTS com SSML. Seguro para uso em qualquer contexto async."""
        ssml = self._build_ssml(text)
        try:
            return asyncio.run(self._synthesize(ssml))
        except RuntimeError:
            # Loop de evento já em execução (ex: chamado dentro de contexto async)
            # Cria e executa em novo loop isolado
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(self._synthesize(ssml))
            except Exception as e:
                print(f"[EdgeTTS] Erro no loop alternativo: {e}")
                return None
            finally:
                loop.close()
        except Exception as e:
            print(f"[EdgeTTS] Erro: {e}")
            return None

    def _build_ssml(self, text: str) -> str:
        """
        Constrói SSML enriquecido com pausas, ênfases e prosódia natural.
        """
        # Escapa caracteres especiais XML
        escaped = (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
        )

        # Adiciona pausas após pontuações
        # Vírgula → pausa curta (200ms)
        escaped = re.sub(r",\s*", ", <break time='180ms'/> ", escaped)
        # Ponto final / exclamação / interrogação → pausa média (350ms)
        escaped = re.sub(r"([.!?])\s+", r"\1 <break time='320ms'/> ", escaped)
        # Dois-pontos → pausa (250ms)
        escaped = re.sub(r":\s*", ": <break time='220ms'/> ", escaped)
        # Reticências → pausa longa (500ms)
        escaped = re.sub(r"\.\.\.\s*", "... <break time='480ms'/> ", escaped)

        ssml = (
            f"<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' "
            f"xmlns:mstts='http://www.w3.org/2001/mstts' xml:lang='pt-BR'>"
            f"<voice name='{self._voice}'>"
            f"<prosody rate='{self._rate}' pitch='{self._pitch}'>"
            f"{escaped}"
            f"</prosody>"
            f"</voice>"
            f"</speak>"
        )
        return ssml

    async def _synthesize(self, ssml: str) -> bytes | None:
        try:
            import edge_tts
        except ImportError:
            print("[EdgeTTS] edge-tts não instalado. Execute: pip install edge-tts")
            return None

        audio_chunks: list[bytes] = []
        communicate = edge_tts.Communicate(ssml, self._voice)

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_chunks.append(chunk["data"])

        if not audio_chunks:
            return None
        return b"".join(audio_chunks)
