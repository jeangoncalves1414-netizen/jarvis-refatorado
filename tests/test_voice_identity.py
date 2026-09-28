from pathlib import Path
import io
import wave

import numpy as np
import pytest

from app.services import identity
from app.services.voice_identity import VoiceIdentityEngine


def test_status_does_not_load_model_or_claim_readiness(tmp_path):
    engine = VoiceIdentityEngine(Path(tmp_path) / "missing.onnx")
    status = engine.status()
    assert status["model_downloaded"] is False
    assert status["ready"] is False
    assert status["minimum_sample_seconds"] == 2.0


def test_voice_match_uses_only_new_embeddings(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "IDENTITY_FILE", Path(tmp_path) / "profiles.json")
    monkeypatch.setattr(identity.voice_identity_engine, "embed", lambda raw, content_type: [1.0, 0.0])
    identity._write({"profiles": [{"id": "new", "name": "Nova", "voice_embeddings": [[1.0, 0.0]]}, {"id": "legacy", "name": "Antiga", "voice_vectors": [[1.0, 0.0]]}]})

    result = identity.IdentityService.identify_audio_bytes(b"not-used", "audio/wav")

    assert result["matched"] is True
    assert result["profile"]["id"] == "new"


def test_voice_similarity_uses_normalized_cosine_score():
    # cosseno 0,72 precisa ficar próximo de 0,86, não virar 0,47 por uma
    # conversão de distância inadequada para embeddings de locutor.
    assert identity._voice_similarity([1.0, 0.0], [0.72, 0.693974]) > 0.85


def test_probable_voice_match_still_requires_confirmation(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "IDENTITY_FILE", Path(tmp_path) / "profiles.json")
    monkeypatch.setattr(identity.voice_identity_engine, "embed", lambda raw, content_type: [1.0, 0.0])
    # Cosseno 0,50 vira score 0,75: limiar forte não deve ser exigido
    # para reconhecimento contextual, mas a UI deve marcar como provável.
    identity._write({"profiles": [{"id": "p1", "name": "Pessoa", "voice_embeddings": [[0.5, 0.866025]]}]})
    result = identity.IdentityService.identify_audio_bytes(b"not-used", "audio/wav")
    assert result["matched"] is True
    assert result["requires_confirmation"] is True


def test_silence_is_rejected_before_embedding(tmp_path):
    engine = VoiceIdentityEngine(Path(tmp_path) / "missing.onnx")
    raw = np.zeros(16_000 * 3, dtype="<i2").tobytes()
    audio = io.BytesIO()
    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16_000)
        wav.writeframes(raw)

    with pytest.raises(ValueError, match="Nenhuma fala detectada"):
        engine.embed(audio.getvalue(), "audio/wav")
