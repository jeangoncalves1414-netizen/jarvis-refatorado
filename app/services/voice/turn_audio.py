"""Local neural speech/turn detection. No microphone, network or model load at import."""
from __future__ import annotations

import hashlib
from pathlib import Path
import numpy as np

MODEL_DIR = Path(__file__).resolve().parents[3] / "data" / "models" / "voice"
MODELS = {
    "smart-turn-v3.2-cpu.onnx": (
        "https://huggingface.co/pipecat-ai/smart-turn-v3/resolve/f766f81d3cfdf7737ac64aad813d91bbfd56bf93/smart-turn-v3.2-cpu.onnx",
        "2bb026316b14a660486a75b1733cd3fbab8c2fd0314dc9af7be49f8cca967e4f",
    ),
    "silero_vad.onnx": (
        "https://raw.githubusercontent.com/snakers4/silero-vad/066409f3d9db45a30d21dfcbf9147826ffdd7052/src/silero_vad/data/silero_vad.onnx",
        "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3",
    ),
}


def install_models() -> None:
    """Explicit setup command; calls never silently download models."""
    import requests
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for name, (url, digest) in MODELS.items():
        target = MODEL_DIR / name
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == digest:
            continue
        response = requests.get(url, timeout=60)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != digest:
            raise ValueError(f"Checksum inválido: {name}")
        temporary = target.with_suffix(".download")
        temporary.write_bytes(response.content)
        temporary.replace(target)


def endpoint_ready(silence: float, probability: float | None) -> bool:
    # Confident endings respond quickly; uncertain/incomplete phrases get more time.
    return silence >= 3.0 or (probability is None and silence >= 2.0) or (
        silence >= .8 and probability is not None and probability >= .8)


class NeuralTurnDetector:
    def __init__(self) -> None:
        import onnxruntime as ort
        options = ort.SessionOptions()
        options.inter_op_num_threads = options.intra_op_num_threads = 1
        options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
        options.add_session_config_entry("session.intra_op.allow_spinning", "0")
        options.add_session_config_entry("session.inter_op.allow_spinning", "0")
        sessions = {}
        for name, (_, digest) in MODELS.items():
            path = MODEL_DIR / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise RuntimeError("Detector local indisponível. Execute python -m app.services.voice.turn_audio --install")
            sessions[name] = ort.InferenceSession(str(path), options, providers=["CPUExecutionProvider"])
        self._turn = sessions["smart-turn-v3.2-cpu.onnx"]
        self._vad = sessions["silero_vad.onnx"]
        self._state = np.zeros((2, 1, 128), dtype=np.float32)
        self._context = np.zeros((1, 64), dtype=np.float32)
        self._pending = np.empty(0, dtype=np.float32)
        self._resample_state = None
        self._last_probability = 0.0

    def speech_probability(self, pcm: bytes, rate: int, width: int) -> float:
        import audioop
        if width != 2:
            pcm = audioop.lin2lin(pcm, width, 2)
        if rate != 16000:
            pcm, self._resample_state = audioop.ratecv(pcm, 2, 1, rate, 16000, self._resample_state)
        samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
        self._pending = np.concatenate((self._pending, samples))
        while self._pending.size >= 512:
            frame = self._pending[:512].reshape(1, 512)
            self._pending = self._pending[512:]
            x = np.concatenate((self._context, frame), axis=1)
            out, self._state = self._vad.run(None, {"input": x, "state": self._state, "sr": np.array(16000, dtype=np.int64)})
            self._context = x[:, -64:]
            self._last_probability = float(out.reshape(-1)[0])
        return self._last_probability

    def completion_probability(self, pcm: bytes, rate: int, width: int) -> float:
        import audioop
        from .vendor.whisper_features import compute_whisper_log_mel_features
        if width != 2:
            pcm = audioop.lin2lin(pcm, width, 2)
        if rate != 16000:
            pcm, _ = audioop.ratecv(pcm, 2, 1, rate, 16000, None)
        audio = np.frombuffer(pcm, dtype="<i2").astype(np.float32)[-128000:] / 32768.0
        audio = np.pad(audio, (max(0, 128000 - audio.size), 0))
        features = compute_whisper_log_mel_features(audio)
        probability = float(self._turn.run(None, {"input_features": features[None]})[0].reshape(-1)[0])
        if not np.isfinite(probability) or not 0 <= probability <= 1:
            raise ValueError("Probabilidade de turno inválida")
        return probability


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    if parser.parse_args().install:
        install_models()
        print("Silero VAD e Smart Turn verificados e instalados.")
