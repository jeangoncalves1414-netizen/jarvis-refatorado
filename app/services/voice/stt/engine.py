from __future__ import annotations

import os
import tempfile
import time
import speech_recognition as sr
from typing import Any
from dataclasses import dataclass

from .filter import filter_stt_hallucinations
from ..audio_convert import AudioConversionError, prepare_audio_for_stt
from app.core.diagnostics import record as diagnostic_record


@dataclass
class STTResult:
    """Resultado da transcrição com metadados."""
    text: str
    language: str | None = None
    duration: float | None = None
    segments: list[dict] | None = None


class STTEngine:
    """
    Motor de Reconhecimento de Fala (STT).
    Providers disponíveis:
    - 'google': Google Speech Recognition (gratuito, sem chave, funciona offline)
    - 'oxyy': Oxyy Whisper API (cloud, requer OXYY_API_KEYS)
    - 'groq': Groq Whisper (cloud, requer GROQ_API_KEY)
    - 'local': faster-whisper offline (sem chave)
    Fallback automático: qualquer falha cloud → Google Speech.
    """

    def __init__(
        self,
        language: str = "pt-BR",
        groq_api_key: str | None = None,
        stt_provider: str = "groq",
        oxyy_api_keys: list[str] | None = None,
        oxyy_base_url: str = "https://api.oxyy.ai/v1",
        oxyy_model: str = "whisper-1",
        energy_threshold: int = 1100,
        dynamic_energy_threshold: bool = True,
        pause_threshold: float = 0.8,
        non_speaking_duration: float = 0.35,
        min_audio_seconds: float = 0.35,
    ) -> None:
        self.language = language
        raw_groq = groq_api_key or os.getenv("GROQ_API_KEYS") or os.getenv("GROQ_API_KEY", "")
        if isinstance(raw_groq, list):
            self.groq_api_keys = [str(k).strip() for k in raw_groq if str(k).strip()]
        else:
            self.groq_api_keys = [k.strip() for k in str(raw_groq).replace("\n", ",").split(",") if k.strip()]
        self.groq_api_key = self.groq_api_keys[0] if self.groq_api_keys else ""
        self.stt_provider = (stt_provider or "groq").lower()
        self.oxyy_api_keys = [str(key).strip() for key in (oxyy_api_keys or []) if str(key).strip()] if oxyy_api_keys else []
        self.oxyy_base_url = (oxyy_base_url or "https://api.oxyy.ai/v1").rstrip("/")
        self.oxyy_model = oxyy_model or "whisper-1"
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
        self._provider_cooldowns: dict[str, float] = {}
        self.last_attempts: list[dict[str, str]] = []

    def _available(self, provider: str) -> bool:
        return time.monotonic() >= self._provider_cooldowns.get(provider, 0.0)

    def _record_attempt(self, provider: str, outcome: str, *, cooldown: bool = False) -> None:
        self.last_attempts.append({"provider": provider, "outcome": outcome})
        self.last_attempts = self.last_attempts[-6:]
        if cooldown:
            self._provider_cooldowns[provider] = time.monotonic() + 30.0
        diagnostic_record("voice.stt", "provider_attempt", "INFO" if outcome == "success" else "WARN", provider=provider, outcome=outcome, cooldown=cooldown)

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

    def transcribe_file(self, file_path: str, return_metadata: bool = False) -> tuple[str | STTResult | None, str | None]:
        """
        Transcreve um arquivo de áudio local. Retorna (texto_filtrado, erro).
        Se return_metadata=True, retorna (STTResult, erro).
        Provider 'google' vai direto ao Google Speech (sem cloud API key).
        """
        if not os.path.exists(file_path):
            return None, "Arquivo de áudio não encontrado."

        raw_text: str | None = None
        self.last_attempts = []

        # -- Provider 'local': faster-whisper offline; se falhar, segue para Groq/Google --
        if self.stt_provider in ("local", "whisper_local"):
            from . import local_whisper
            raw_text, err = local_whisper.transcribe_file(file_path, self.language)
            self._record_attempt("local", "success" if raw_text else "failed")
            if raw_text:
                filtered = filter_stt_hallucinations(raw_text)
                if not filtered:
                    return None, "Áudio descartado pelo filtro de ruído/silêncio."
                return filtered, None
            if err:
                print(f"[STT Engine] STT local indisponível ({err}); usando fallback em nuvem...")

        # ── Provider 'google': vai direto ao Google Speech (gratuito, sem chave) ──
        if self.stt_provider == "google":
            wav_temp: str | None = None
            try:
                try:
                    stt_path, is_temp = prepare_audio_for_stt(file_path)
                    if is_temp:
                        wav_temp = stt_path
                except AudioConversionError as exc:
                    return None, f"Erro na conversão de áudio: {exc.message}"
                raw_text = self._transcribe_google(stt_path)
                self._record_attempt("google", "success" if raw_text else "failed")
            finally:
                if wav_temp:
                    try:
                        os.remove(wav_temp)
                    except OSError:
                        pass
            if not raw_text:
                return None, "Google Speech não conseguiu entender o áudio."
            filtered = filter_stt_hallucinations(raw_text)
            if not filtered:
                return None, "Áudio descartado pelo filtro de ruído/silêncio."
            return filtered, None

        # 1. Provider escolhido (ambos suportam webm/mp3/ogg diretamente).
        if self.stt_provider == "oxyy" and self.oxyy_api_keys and not self._available("oxyy"):
            self._record_attempt("oxyy", "cooldown")
            if self.groq_api_keys and self._available("groq"):
                raw_text = self._transcribe_groq(file_path)
                self._record_attempt("groq", "success" if raw_text else "failed")
        elif self.stt_provider == "oxyy" and self.oxyy_api_keys:
            result = self._transcribe_oxyy(file_path, return_metadata=return_metadata)
            if return_metadata and result:
                self._record_attempt("oxyy", "success")
                return result, None
            raw_text = result.text if isinstance(result, STTResult) else result if result else None
            self._record_attempt("oxyy", "success" if raw_text else "failed", cooldown=not bool(raw_text))
            if not raw_text and self.groq_api_keys:
                print("[STT Engine] Oxyy falhou; acionando fallback Groq Whisper...")
                raw_text = self._transcribe_groq(file_path)
                self._record_attempt("groq", "success" if raw_text else "failed")
        elif self.groq_api_keys and self._available("groq"):
            raw_text = self._transcribe_groq(file_path)
            self._record_attempt("groq", "success" if raw_text else "failed")

        if raw_text:
            filtered = filter_stt_hallucinations(raw_text)
            if not filtered:
                return None, "Áudio descartado pelo filtro de ruído/silêncio."
            return filtered, None

        # 2. Fallback: Google STT (apenas quando arquivo já é WAV ou ffmpeg disponível)
        wav_temp2: str | None = None
        try:
            try:
                stt_path, is_temp = prepare_audio_for_stt(file_path)
                if is_temp:
                    wav_temp2 = stt_path
            except AudioConversionError as exc:
                if not self.groq_api_keys:
                    return None, "Configure GROQ_API_KEY no .env para usar STT de voz no navegador."
                return None, f"Erro na conversão de áudio: {exc.message}"

            raw_text = self._transcribe_google(stt_path)
            self._record_attempt("google", "success" if raw_text else "failed")
        finally:
            if wav_temp2:
                try:
                    os.remove(wav_temp2)
                except OSError:
                    pass

        if not raw_text:
            attempted = ", ".join(f"{item['provider']}:{item['outcome']}" for item in self.last_attempts)
            return None, f"Não foi possível entender o áudio. Tentativas: {attempted or 'nenhuma'}."

        filtered = filter_stt_hallucinations(raw_text)
        if not filtered:
            return None, "Áudio descartado pelo filtro de ruído/silêncio."

        return filtered, None

    def _transcribe_oxyy(self, file_path: str, return_metadata: bool = False) -> STTResult | str | None:
        try:
            from openai import OpenAI
            for key in self.oxyy_api_keys:
                try:
                    client = OpenAI(api_key=key, base_url=self.oxyy_base_url)
                    with open(file_path, "rb") as file:
                        kwargs: dict[str, Any] = {
                            "model": self.oxyy_model,
                            "file": (os.path.basename(file_path), file.read()),
                            "response_format": "verbose_json" if return_metadata else "json",
                            "timestamp_granularities": ["segment"] if return_metadata else [],
                        }
                        # Não forçar language para permitir auto-detection
                        if "pt" in self.language.lower() and not return_metadata:
                            kwargs["language"] = "pt"
                        transcription = client.audio.transcriptions.create(**kwargs)

                    text = getattr(transcription, "text", None) or (transcription.get("text") if isinstance(transcription, dict) else None)
                    if not text:
                        continue

                    if return_metadata:
                        language = getattr(transcription, "language", None) or (transcription.get("language") if isinstance(transcription, dict) else None)
                        duration = getattr(transcription, "duration", None) or (transcription.get("duration") if isinstance(transcription, dict) else None)
                        segments = getattr(transcription, "segments", None) or (transcription.get("segments") if isinstance(transcription, dict) else None)
                        return STTResult(
                            text=str(text).strip(),
                            language=language,
                            duration=duration,
                            segments=segments
                        )
                    else:
                        return str(text).strip()
                except Exception as exc:
                    print(f"[STT Engine] Oxyy chave falhou ({exc}); tentando a próxima...")
            return None
        except Exception as exc:
            print(f"[STT Engine] Oxyy Whisper indisponível ({exc}), tentando fallback...")
            return None


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
        except ImportError:
            print("[STT Engine] Pacote groq não instalado.")
            return None

        if not self.groq_api_keys:
            print("[STT Engine] Nenhuma chave Groq disponível.")
            return None

        for key in self.groq_api_keys:
            try:
                client = Groq(api_key=key)
                with open(file_path, "rb") as file:
                    transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(file_path), file.read()),
                        model="whisper-large-v3-turbo",
                        response_format="json",
                        language="pt" if "pt" in self.language.lower() else "en",
                    )
                    text = transcription.text.strip()
                    if text:
                        return text
            except Exception as e:
                print(f"[STT Engine] Groq Whisper ({key[:8]}...) falhou: {e}; tentando próxima chave...")
                continue

        print("[STT Engine] Todas as chaves Groq Whisper falharam, tentando fallback...")
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
