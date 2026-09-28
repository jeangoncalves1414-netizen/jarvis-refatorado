from __future__ import annotations

import os
from unittest.mock import MagicMock
from app.services.voice.stt.engine import STTEngine
from app.storage.runtime_settings import get_stt_settings, set_stt_provider, _VALID_STT_PROVIDERS


def test_valid_stt_providers_includes_whisper_local_and_google():
    assert "whisper_local" in _VALID_STT_PROVIDERS
    assert "google" in _VALID_STT_PROVIDERS
    assert "groq" in _VALID_STT_PROVIDERS
    assert "oxyy" in _VALID_STT_PROVIDERS


def test_set_and_get_stt_provider_whisper_local():
    original = os.getenv("STT_PROVIDER", "google")
    try:
        set_stt_provider("whisper_local")
        assert os.environ.get("STT_PROVIDER") == "whisper_local"
        settings = get_stt_settings()
        assert settings["stt_provider"] == "whisper_local"
    finally:
        set_stt_provider(original)


def test_whisper_local_success(tmp_path, monkeypatch):
    clip = tmp_path / "voice.wav"
    clip.write_bytes(b"RIFFdummywavdata")
    engine = STTEngine(stt_provider="whisper_local")

    monkeypatch.setattr(engine, "_transcribe_whisper_local", lambda _f: ("Olá mundo Jarvis", None))
    text, error = engine.transcribe_file(str(clip))

    assert text == "Olá mundo Jarvis"
    assert error is None
    assert engine.last_attempts[0] == {"provider": "whisper_local", "outcome": "success"}


def test_whisper_local_fallback_to_google(tmp_path, monkeypatch):
    clip = tmp_path / "voice.wav"
    clip.write_bytes(b"RIFFdummywavdata")
    engine = STTEngine(stt_provider="whisper_local")

    # whisper_local returns error (e.g. package missing)
    monkeypatch.setattr(engine, "_transcribe_whisper_local", lambda _f: (None, "openai-whisper não instalado"))
    # google succeeds
    monkeypatch.setattr(engine, "_transcribe_google", lambda _f: "Transcrição via Google")

    text, error = engine.transcribe_file(str(clip))

    assert text == "Transcrição via Google"
    assert error is None
    assert {"provider": "whisper_local", "outcome": "failed"} in engine.last_attempts
    assert {"provider": "google", "outcome": "success"} in engine.last_attempts


def test_google_provider_direct(tmp_path, monkeypatch):
    clip = tmp_path / "voice.wav"
    clip.write_bytes(b"RIFFdummywavdata")
    engine = STTEngine(stt_provider="google")

    monkeypatch.setattr(engine, "_transcribe_google", lambda _f: "Comando executado com sucesso")
    text, error = engine.transcribe_file(str(clip))

    assert text == "Comando executado com sucesso"
    assert error is None
    assert engine.last_attempts[0] == {"provider": "google", "outcome": "success"}
