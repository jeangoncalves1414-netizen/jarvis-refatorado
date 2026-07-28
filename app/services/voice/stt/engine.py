from __future__ import annotations

import os
import tempfile
import speech_recognition as sr
from typing import Any

from .filter import filter_stt_hallucinations
from ..audio_convert import AudioConversionError, prepare_audio_for_stt


class STTEngine:
    """
    Motor de Reconhecimento de Fala (STT).
    Utiliza Groq Whisper (whisper-large-v3-turbo) como primário
    e Google Speech Recognition como fallback de alta disponibilidade.
    """

    def __init__(
        self,
        language: str = "pt-BR",
        groq_api_key: str | None = None,
        energy_threshold: int = 1100,
        dynamic_energy_threshold: bool = True,
        pause_threshold: float = 0.8,
        non_speaking_duration: float = 0.35,
        min_audio_seconds: float = 0.35,
    ) -> None:
        self.language = language
        self.groq_api_key = groq_api_key or os.getenv("GROQ_API_KEY", "")
        self.recognizer = sr.Recognizer()

        self.energy_threshold = max(150, min(8000, int(energy_threshold or 1100)))
        self.dynamic_energy_threshold = bool(dynamic_energy_threshold)
        self.pause_threshold = max(0.25, min(3.0, float(pause_threshold or 0.8)))
        self.non_speaking_duration = max(0.1, min(2.0, float(non_speaking_duration or 0.35)))
        self.min_audio_seconds = max(0.05, min(3.0, float(min_audio_seconds or 0.35)))

        self.recognizer.energy_threshold = self.energy_threshold
        self.recognizer.dynamic_energy_threshold = self.dynamic_energy_threshold
        self.recognizer.dynamic_energy_adjustment_damping = 0.15
        self.recognizer.pause_threshold = self.pause_threshold
        self.recognizer.non_speaking_duration = self.non_speaking_duration

    def calibrate(self, duration: float = 0.8) -> None:
        """Ajusta o reconhecedor ao ruído ambiente respeitando o limite mínimo."""
        try:
            with sr.Microphone() as source:
                print(f"[STT Engine] Calibrando ruído ambiente ({duration}s)...")
                self.recognizer.adjust_for_ambient_noise(source, duration=duration)
                if self.recognizer.energy_threshold < self.energy_threshold:
                    self.recognizer.energy_threshold = self.energy_threshold
                print(f"[STT Engine] Calibração concluída. Threshold final: {self.recognizer.energy_threshold}")
        except Exception as e:
            print(f"[STT Engine] Erro na calibração: {e}")

    def transcribe_file(self, file_path: str) -> tuple[str | None, str | None]:
        """
        Transcreve um arquivo de áudio local. Retorna (texto_filtrado, erro).
        Prefere Groq Whisper (suporta webm nativamente). Fallback para Google STT apenas em WAV.
        """
        if not os.path.exists(file_path):
            return None, "Arquivo de áudio não encontrado."

        raw_text: str | None = None

        # 1. Tentar Groq Whisper (suporta webm, mp3, ogg diretamente)
        if self.groq_api_key:
            raw_text = self._transcribe_groq(file_path)
            if raw_text:
                filtered = filter_stt_hallucinations(raw_text)
                if not filtered:
                    return None, "Áudio descartado pelo filtro de ruído/silêncio."
                return filtered, None

        # 2. Fallback: Google STT (apenas quando arquivo já é WAV ou ffmpeg disponível)
        suffix = os.path.splitext(file_path)[1].lower()
        wav_temp: str | None = None
        try:
            try:
                stt_path, is_temp = prepare_audio_for_stt(file_path)
                if is_temp:
                    wav_temp = stt_path
            except AudioConversionError as exc:
                if not self.groq_api_key:
                    return None, "Configure GROQ_API_KEY no .env para usar STT de voz no navegador."
                return None, f"Erro na conversão de áudio: {exc.message}"

            raw_text = self._transcribe_google(stt_path)
        finally:
            if wav_temp:
                try:
                    os.remove(wav_temp)
                except OSError:
                    pass

        if not raw_text:
            return None, "Não foi possível entender o áudio."

        filtered = filter_stt_hallucinations(raw_text)
        if not filtered:
            return None, "Áudio descartado pelo filtro de ruído/silêncio."

        return filtered, None


    def listen_and_transcribe(
        self, timeout: float = 5.0, phrase_time_limit: float = 10.0
    ) -> str | None:
        """
        Escuta diretamente do microfone e retorna o texto transcrevido e filtrado.
        """
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.8)
                print("[STT Engine] Ouvindo microfone...")
                audio = self.recognizer.listen(
                    source, timeout=timeout, phrase_time_limit=phrase_time_limit
                )

                # Verifica duração mínima do áudio
                duration = len(audio.get_raw_data()) / (audio.sample_rate * audio.sample_width)
                if duration < self.min_audio_seconds:
                    return None

                temp_dir = tempfile.gettempdir()
                temp_file = os.path.join(temp_dir, f"jarvis_stt_{os.urandom(4).hex()}.wav")

                with open(temp_file, "wb") as f:
                    f.write(audio.get_wav_data())

                text, _err = self.transcribe_file(temp_file)

                try:
                    os.remove(temp_file)
                except Exception:
                    pass

                return text
        except sr.WaitTimeoutError:
            print("[STT Engine] Timeout sem fala detectada.")
            return None
        except Exception as e:
            print(f"[STT Engine] Erro ao ouvir e transcrever: {e}")
            return None

    def _transcribe_groq(self, file_path: str) -> str | None:
        try:
            from groq import Groq

            client = Groq(api_key=self.groq_api_key)

            with open(file_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), file.read()),
                    model="whisper-large-v3-turbo",
                    response_format="json",
                    language="pt" if "pt" in self.language.lower() else "en",
                )
                return transcription.text.strip()
        except Exception as e:
            print(f"[STT Engine] Groq Whisper falhou ({e}), tentando fallback...")
            return None

    def _transcribe_google(self, file_path: str) -> str | None:
        try:
            with sr.AudioFile(file_path) as source:
                audio = self.recognizer.record(source)
            return self.recognizer.recognize_google(audio, language=self.language)
        except sr.UnknownValueError:
            return None
        except Exception as e:
            print(f"[STT Engine] Google Speech erro: {e}")
            return None
