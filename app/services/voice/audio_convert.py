from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path


class AudioConversionError(Exception):
    """Raised when browser audio cannot be converted for Google STT."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


_BROWSER_FORMATS = {".webm", ".ogg", ".mp3", ".m4a", ".opus", ".weba"}


def _ffmpeg_path() -> str | None:
    if shutil.which("ffmpeg"):
        return "ffmpeg"
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _convert_with_ffmpeg(input_path: str, sample_rate: int) -> str | None:
    ffmpeg = _ffmpeg_path()
    if not ffmpeg:
        return None

    out_path = os.path.join(tempfile.gettempdir(), f"jarvis_wav_{os.urandom(4).hex()}.wav")
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        input_path,
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-vn",
        out_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
        if result.returncode == 0 and os.path.exists(out_path):
            return out_path
    except Exception:
        pass
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except OSError:
            pass
    return None


def _convert_with_pydub(input_path: str, sample_rate: int) -> str | None:
    try:
        from pydub import AudioSegment
    except ImportError:
        return None

    out_path = os.path.join(tempfile.gettempdir(), f"jarvis_wav_{os.urandom(4).hex()}.wav")
    try:
        audio = AudioSegment.from_file(input_path)
        audio = audio.set_frame_rate(sample_rate).set_channels(1)
        audio.export(out_path, format="wav")
        if os.path.exists(out_path):
            return out_path
    except Exception:
        pass
    if os.path.exists(out_path):
        try:
            os.remove(out_path)
        except OSError:
            pass
    return None


def convert_to_wav(input_path: str, sample_rate: int = 16000) -> str | None:
    """Convert audio file to mono WAV. Returns output path or None on failure."""
    src = Path(input_path)
    if not src.exists():
        return None

    if src.suffix.lower() in {".wav", ".wave"}:
        return str(src)

    return _convert_with_ffmpeg(str(src), sample_rate) or _convert_with_pydub(str(src), sample_rate)


def _conversion_error_message(suffix: str) -> str:
    return (
        f"Não foi possível converter o áudio ({suffix}). "
        "Instale o ffmpeg ou configure GROQ_API_KEY para transcrição alternativa."
    )


def prepare_audio_for_stt(file_path: str) -> tuple[str, bool]:
    """
    Returns (path_for_stt, is_temp).
    Converts webm/ogg/mp3 to wav when ffmpeg or pydub is available.
    Raises AudioConversionError when conversion is required but fails.
    """
    suffix = Path(file_path).suffix.lower()
    if suffix not in _BROWSER_FORMATS:
        return file_path, False

    wav = convert_to_wav(file_path)
    if wav:
        return wav, True

    raise AudioConversionError(_conversion_error_message(suffix or "desconhecido"))
