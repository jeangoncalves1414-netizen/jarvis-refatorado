import pytest
from app.services.face_identity import FaceIdentityEngine
from app.services.identity import _match_voice


def test_enrollment_rejects_multiple_people(monkeypatch):
    engine = FaceIdentityEngine()
    monkeypatch.setattr(engine, 'extract', lambda _: [{'embedding': [1., 0.]}] * 2)
    with pytest.raises(ValueError, match='exatamente um rosto'):
        engine.embed(b'frame')


def test_legacy_face_samples_are_not_compared_to_sface():
    result = _match_voice([1., 0.], [{'id': 'legacy', 'face_vectors': [[1., 0.]]}],
                          field='face_embeddings_sface', threshold=0.75)
    assert not result['matched']


def test_face_ambiguity_is_rejected():
    profiles = [{'id': name, 'face_embeddings_sface': [[1., 0.]]} for name in ['Jean', 'Irmã']]
    result = _match_voice([1., 0.], profiles, field='face_embeddings_sface', threshold=0.75)
    assert result['reason'] == 'ambiguous'
    assert result['profile'] is None


def test_missing_models_fail_without_downloading(tmp_path):
    with pytest.raises(ValueError, match='Prepare o modelo'):
        FaceIdentityEngine(tmp_path).extract(b'frame')
