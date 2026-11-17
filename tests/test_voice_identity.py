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


def test_fbank_matches_wespeaker_pcm_scale_and_hamming_window(monkeypatch):
    import kaldi_native_fbank as knf
    class Bank:
        num_frames_ready = 2
        def __init__(self, options):
            assert options.frame_opts.window_type == 'hamming'
            assert options.frame_opts.snip_edges
            assert options.mel_opts.num_bins == 80
        def accept_waveform(self, rate, samples):
            assert rate == 16000
            np.testing.assert_allclose(samples, [0, 16384, -32768])
        def input_finished(self): pass
        def get_frame(self, i): return np.full(80, i, dtype='float32')
    monkeypatch.setattr(knf, 'OnlineFbank', Bank)
    features = VoiceIdentityEngine._fbank(np.array([0, .5, -1], dtype='float32'))
    np.testing.assert_allclose(features.mean(axis=0), 0)


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


def test_similar_people_are_unknown_not_arbitrarily_selected():
    profiles = [{"id": "jean", "voice_embeddings": [[1., 0.]]},
                {"id": "sister", "voice_embeddings": [[0.99, 0.1]]}]
    for order in (profiles, profiles[::-1]):
        result = identity._match_voice([1., 0.], order)
        assert result['matched'] is False
        assert result['profile'] is None
        assert result['reason'] == 'ambiguous'


def test_multiple_samples_of_same_person_are_not_competing_people():
    result = identity._match_voice([1., 0.], [{"id": "jean", "voice_embeddings": [[1., 0.], [0.99, 0.1]]}])
    assert result['matched'] is True


def test_invalid_embedding_cannot_match():
    result = identity._match_voice([float('nan'), 0.], [{"id": "jean", "voice_embeddings": [[1., 0.]]}])
    assert result['matched'] is False


@pytest.mark.parametrize('vector', [[None], ['bad'], [True], [0., 0.], [float('inf'), 0.]])
def test_malformed_query_is_unknown(vector):
    assert not identity._match_voice(vector, [{'id': 'p', 'voice_embeddings': [[1., 0.]]}])['matched']


def test_single_outlier_cannot_override_consistent_references():
    profiles = [{'id': 'jean', 'voice_embeddings': [[1., 0.], [1., 0.], [0., 1.]]},
                {'id': 'sister', 'voice_embeddings': [[0., 1.], [0., 1.]]}]
    result = identity._match_voice([0., 1.], profiles)
    assert result['matched'] and result['profile']['id'] == 'sister'


def test_corrupt_saved_reference_does_not_break_other_profiles():
    result = identity._match_voice([1., 0.], [
        {'id': 'bad', 'voice_embeddings': [None, ['bad', 0], [False, False]]},
        {'id': 'good', 'voice_embeddings': [[1., 0.]]}])
    assert result['profile']['id'] == 'good'


def test_enrollment_rejects_inconsistent_voice_without_changing_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, 'IDENTITY_FILE', tmp_path / 'profiles.json')
    profile = identity.IdentityService.enroll_admin('Jean', 'password123')['profile']
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *a: [1., 0.])
    assert identity.IdentityService.add_sample(profile['id'], 'password123', 'voice', 'data:audio/wav;base64,AA==')['ok']
    before = identity.IDENTITY_FILE.read_bytes()
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *a: [0., 1.])
    result = identity.IdentityService.add_sample(profile['id'], 'password123', 'voice', 'data:audio/wav;base64,AA==')
    assert not result['ok'] and 'difere' in result['error']
    assert identity.IDENTITY_FILE.read_bytes() == before


def test_same_voice_cannot_be_silently_enrolled_as_two_people(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, 'IDENTITY_FILE', tmp_path / 'profiles.json')
    first = identity.IdentityService.enroll_admin('Jean', 'password123')['profile']
    second = identity.IdentityService.enroll_profile('Irmã', 'user', 'password123')['profile']
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *a: [1., 0.])
    assert identity.IdentityService.add_sample(first['id'], 'password123', 'voice', 'data:audio/wav;base64,AA==')['ok']
    result = identity.IdentityService.add_sample(second['id'], 'password123', 'voice', 'data:audio/wav;base64,AA==')
    assert not result['ok'] and 'outro perfil' in result['error']


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
