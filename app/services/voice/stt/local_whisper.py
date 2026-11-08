"""STT local com faster-whisper (offline, sem chave de API).

O modelo é baixado pelo faster-whisper na PRIMEIRA transcrição (tiny ~75 MB,
base ~145 MB, small ~480 MB, medium ~1.5 GB). Depois fica em cache e funciona
sem internet.
"""
from __future__ import annotations

import importlib.util
import logging
import os
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

VALID_MODELS = ("tiny", "base", "small", "medium")
DEFAULT_MODEL = "base"
VALID_DEVICES = ("auto", "cpu", "cuda")
MODEL_SIZE_HINT = {"tiny": "~75 MB", "base": "~145 MB", "small": "~480 MB", "medium": "~1,5 GB"}

_lock = threading.Lock()
_models: dict[tuple[str, str], object] = {}


def is_available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def unavailable_reason() -> str:
    return "Desligado: biblioteca faster-whisper não instalada (pip install faster-whisper)."


def configured_model() -> str:
    value = os.getenv("STT_LOCAL_MODEL", DEFAULT_MODEL).strip().lower()
    return value if value in VALID_MODELS else DEFAULT_MODEL


def configured_device() -> str:
    value = os.getenv("STT_LOCAL_DEVICE", "auto").strip().lower()
    return value if value in VALID_DEVICES else "auto"


def model_cached(model: str | None = None) -> bool:
    """True se o modelo já foi baixado para o cache do Hugging Face."""
    name = model or configured_model()
    root = Path(os.getenv("HF_HOME") or (Path.home() / ".cache" / "huggingface")) / "hub"
    return (root / f"models--Systran--faster-whisper-{name}").exists()


def _cuda_available() -> bool:
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def _load(model: str, device: str):
    from faster_whisper import WhisperModel

    resolved = "cuda" if device == "cuda" or (device == "auto" and _cuda_available()) else "cpu"
    key = (model, resolved)
    with _lock:
        loaded = _models.get(key)
        if loaded is None:
            if not model_cached(model):
                logger.warning(
                    "STT local: baixando o modelo '%s' (%s) na primeira vez. Isso pode demorar; depois funciona offline.",
                    model, MODEL_SIZE_HINT.get(model, ""),
                )
            compute = "float16" if resolved == "cuda" else "int8"
            loaded = WhisperModel(model, device=resolved, compute_type=compute)
            _models[key] = loaded
        return loaded


def transcribe_file(file_path: str, language: str = "pt-BR") -> tuple[str | None, str | None]:
    """Retorna (texto, erro)."""
    if not is_available():
        return None, unavailable_reason()
    try:
        model = _load(configured_model(), configured_device())
        lang = (language or "pt").split("-")[0].lower() or "pt"
        segments, _info = model.transcribe(
            file_path,
            language=lang,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400},
            condition_on_previous_text=False,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return (text or None), None
    except Exception as exc:
        return None, f"Falha no STT local: {type(exc).__name__}: {exc}"
