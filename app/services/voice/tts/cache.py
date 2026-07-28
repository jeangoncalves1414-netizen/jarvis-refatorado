from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


class TTSCache:
    """
    Sistema de cache de áudio para evitar resintetizar falas repetidas
    (ex: "Dito e feito, Sir", "Aguarde um momento").
    """

    def __init__(self, cache_dir: str | Path = "data/tts_cache") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _generate_hash(self, text: str, voice: str, provider: str = "edge") -> str:
        clean_text = text.strip().lower()
        key = f"{clean_text}|{voice}|{provider}"
        return hashlib.md5(key.encode("utf-8")).hexdigest()

    def get_cached_file(self, text: str, voice: str, provider: str = "edge") -> Path | None:
        if not text.strip():
            return None

        file_hash = self._generate_hash(text, voice, provider)
        cached_path = self.cache_dir / f"{file_hash}.mp3"
        if not cached_path.exists():
            # Tenta variante .wav
            cached_path = self.cache_dir / f"{file_hash}.wav"

        if cached_path.exists():
            return cached_path
        return None

    def save_to_cache(
        self, text: str, voice: str, source_audio_path: Path | str, provider: str = "edge"
    ) -> Path:
        file_hash = self._generate_hash(text, voice, provider)
        source_path = Path(source_audio_path)
        ext = source_path.suffix or ".mp3"
        cached_path = self.cache_dir / f"{file_hash}{ext}"

        shutil.copy2(str(source_path), str(cached_path))
        return cached_path

    def clear_cache(self) -> None:
        for f in self.cache_dir.glob("*.*"):
            if f.suffix.lower() in (".mp3", ".wav"):
                try:
                    f.unlink()
                except Exception:
                    pass
