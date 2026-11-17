"""Identificação local de locutor, baseada em embeddings ONNX.

O modelo só é carregado quando uma amostra de voz é cadastrada ou verificada.
Nenhum áudio ou embedding é enviado para serviços externos; o único download
opcional é o arquivo público do modelo, iniciado explicitamente pela interface.
"""
from __future__ import annotations

from io import BytesIO
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.request import urlopen

MODEL_ID = "wespeaker-resnet34-lm-v1"
MODEL_URL = "https://huggingface.co/Wespeaker/wespeaker-resnet34-LM/resolve/main/voxceleb_resnet34_LM.onnx?download=true"
MODEL_PATH = Path("data") / "models" / "voxceleb_resnet34_LM.onnx"
MIN_AUDIO_SECONDS = 2.0
MIN_SHORT_TURN_SECONDS = 1.0
MIN_MODEL_BYTES = 1_000_000
MIN_SPEECH_SECONDS = 0.7
MIN_SIGNAL_RMS = 0.006


class VoiceIdentityError(ValueError):
    """Erro seguro e compreensível da biometria de voz."""


class VoiceIdentityEngine:
    def __init__(self, model_path: Path = MODEL_PATH) -> None:
        self.model_path = model_path
        self._session: Any = None

    def status(self) -> dict[str, Any]:
        from app.services.voice_segmentation import engine as segmentation
        missing: list[str] = []
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            missing.append("onnxruntime")
        try:
            import kaldi_native_fbank  # noqa: F401
        except ImportError:
            missing.append("kaldi-native-fbank")
        return {
            "ok": True,
            "model_id": MODEL_ID,
            "ready": not missing and self.model_path.is_file() and self.model_path.stat().st_size >= MIN_MODEL_BYTES and segmentation.model_path.is_file(),
            "segmentation_downloaded": segmentation.model_path.is_file(),
            "model_downloaded": self.model_path.is_file(),
            "model_size_bytes": self.model_path.stat().st_size if self.model_path.is_file() else 0,
            "missing_dependencies": missing,
            "minimum_sample_seconds": MIN_AUDIO_SECONDS,
        }

    def install_model(self) -> dict[str, Any]:
        current = self.status()
        if current["missing_dependencies"]:
            raise VoiceIdentityError("Dependências locais ausentes: " + ", ".join(current["missing_dependencies"]))
        from app.services.voice_segmentation import engine as segmentation
        try:
            segmentation.install()
        except Exception as exc:
            raise VoiceIdentityError("Não foi possível preparar a segmentação local de voz. Tente novamente.") from exc
        current = self.status()
        if current["ready"]:
            return current
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.model_path.with_suffix(".download")
        try:
            with urlopen(MODEL_URL, timeout=90) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            if temporary.stat().st_size < MIN_MODEL_BYTES:
                raise VoiceIdentityError("O download do modelo parece incompleto.")
            temporary.replace(self.model_path)
        except VoiceIdentityError:
            temporary.unlink(missing_ok=True)
            raise
        except Exception as exc:
            temporary.unlink(missing_ok=True)
            raise VoiceIdentityError("Não foi possível baixar o modelo local de voz. Tente novamente.") from exc
        return self.status()

    def embed(self, raw: bytes, content_type: str = "audio/webm") -> list[float]:
        samples = self._decode_audio(raw, content_type)
        return self.embed_samples(samples)

    def embed_samples(self, samples, *, activity=None, short_turn=False) -> list[float]:
        """Reuse decoded audio; activity is only supplied by local segmentation."""
        if short_turn and len(samples) < int(16_000 * MIN_SHORT_TURN_SECONDS):
            raise VoiceIdentityError("A fala durou menos de um segundo. Tente uma frase um pouco mais longa.")
        if not short_turn and len(samples) < int(16_000 * MIN_AUDIO_SECONDS):
            raise VoiceIdentityError("Fale por pelo menos 2 segundos para criar uma impressão vocal confiável.")
        import numpy as np
        if not np.isfinite(samples).all() or float(np.sqrt(np.mean(np.square(samples)))) < MIN_SIGNAL_RMS:
            raise VoiceIdentityError("Nenhuma fala detectada. Fale em volume normal e tente novamente.")
        from app.services.voice_segmentation import engine as segmentation
        try:
            if activity is None:
                activity = segmentation.analyze(samples)
        except ValueError as exc:
            raise VoiceIdentityError(str(exc)) from exc
        if activity['overlap_seconds'] >= 0.2 or activity['multiple_speakers']:
            raise VoiceIdentityError("Mais de uma voz detectada. Fale uma pessoa por vez para identificar quem falou.")
        if activity['speech_seconds'] < MIN_SPEECH_SECONDS:
            raise VoiceIdentityError("Nenhuma fala detectada por tempo suficiente. Fale por alguns segundos.")
        session = self._get_session()
        features = self._fbank(samples)
        if len(features) < 20:
            raise VoiceIdentityError("A amostra de voz ficou curta demais. Tente novamente em um local silencioso.")
        import numpy as np

        embedding = session.run(["embs"], {"feats": features[None, :, :]})[0][0]
        norm = float(np.linalg.norm(embedding))
        if not norm:
            raise VoiceIdentityError("Não foi possível extrair uma impressão vocal desta amostra.")
        return (embedding / norm).astype("float32").tolist()

    def _get_session(self) -> Any:
        if not self.status()["ready"]:
            raise VoiceIdentityError("O modelo local de identificação ainda não foi preparado.")
        if self._session is None:
            import onnxruntime as ort

            options = ort.SessionOptions()
            options.inter_op_num_threads = 1
            options.intra_op_num_threads = 1
            self._session = ort.InferenceSession(str(self.model_path), sess_options=options, providers=["CPUExecutionProvider"])
        return self._session

    @staticmethod
    def _decode_audio(raw: bytes, content_type: str) -> Any:
        # WAV PCM não depende de ffmpeg/pydub: mantém a função utilizável em
        # instalações mínimas e é especialmente útil nos testes locais.
        if "wav" in content_type:
            try:
                import wave
                import numpy as np

                with wave.open(BytesIO(raw), "rb") as wav:
                    if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16_000:
                        raise ValueError("WAV precisa ser convertido")
                    return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype("float32") / 32768.0
            except Exception:
                # Outros WAVs ainda podem ser normalizados pelo pydub abaixo.
                pass
        suffix = ".ogg" if "ogg" in content_type else ".mp3" if "mpeg" in content_type else ".webm"
        source_path = ""
        converted_path = ""
        try:
            # Reutiliza o conversor do STT. Ele localiza tanto um ffmpeg do
            # sistema quanto o binário que já vem com imageio-ffmpeg.
            from app.services.voice.audio_convert import convert_to_wav
            import numpy as np
            import wave

            with tempfile.NamedTemporaryFile(prefix="jarvis_identity_", suffix=suffix, delete=False) as source:
                source.write(raw)
                source_path = source.name
            converted_path = convert_to_wav(source_path, sample_rate=16_000) or ""
            if not converted_path:
                raise VoiceIdentityError("O conversor local não conseguiu abrir este áudio WebM. Feche e reinicie o Jarvis; se persistir, envie o log de diagnóstico.")
            with wave.open(converted_path, "rb") as wav:
                if wav.getnchannels() != 1 or wav.getsampwidth() != 2 or wav.getframerate() != 16_000:
                    raise VoiceIdentityError("O conversor retornou um formato de áudio inesperado.")
                return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype("float32") / 32768.0
        except VoiceIdentityError:
            raise
        except Exception as exc:
            raise VoiceIdentityError("Não foi possível preparar o áudio da voz para identificação.") from exc
        finally:
            for path in {source_path, converted_path}:
                if path:
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @staticmethod
    def _fbank(samples: Any) -> Any:
        import kaldi_native_fbank as knf
        import numpy as np

        options = knf.FbankOptions()
        options.frame_opts.samp_freq = 16_000
        options.frame_opts.dither = 0.0
        options.frame_opts.frame_length_ms = 25
        options.frame_opts.frame_shift_ms = 10
        options.frame_opts.window_type = 'hamming'
        options.frame_opts.snip_edges = True
        options.mel_opts.num_bins = 80
        fbank = knf.OnlineFbank(options)
        # Match WeSpeaker's reference infer_onnx.py: PCM scale and Hamming window.
        fbank.accept_waveform(16_000, np.asarray(samples, dtype='float32') * 32768.0)
        fbank.input_finished()
        frames = [fbank.get_frame(index) for index in range(fbank.num_frames_ready)]
        features = np.asarray(frames, dtype="float32")
        return features - features.mean(axis=0, keepdims=True)


engine = VoiceIdentityEngine()
