import numpy as np
import pytest

from app.services.voice_segmentation import VoiceSegmentationEngine
from app.services.voice_identity import VoiceIdentityEngine, VoiceIdentityError


class Session:
    def __init__(self, classes):
        self.classes = classes

    def run(self, *args):
        return [np.eye(7, dtype=np.float32)[self.classes][None, :, :]]


@pytest.mark.parametrize('classes,multiple,overlap', [
    ([0] * 589, False, False),
    ([1] * 589, False, False),
    ([1] * 200 + [2] * 389, True, False),
    ([4] * 589, True, True),
])
def test_segment_classes_distinguish_silence_turn_change_and_overlap(classes, multiple, overlap):
    engine = VoiceSegmentationEngine()
    engine._session = Session(classes)
    result = engine.analyze(np.ones(160000, dtype=np.float32))
    assert result['multiple_speakers'] is multiple
    assert (result['overlap_seconds'] > .2) is overlap


def test_padded_tail_cannot_introduce_another_speaker():
    engine = VoiceSegmentationEngine()
    engine._session = Session([1] * 115 + [4] * (589 - 115))
    result = engine.analyze(np.ones(32000, dtype=np.float32))
    assert not result['multiple_speakers']
    assert result['overlap_seconds'] == 0


def test_mixed_voice_never_reaches_identity_embedding(monkeypatch):
    from app.services import voice_segmentation
    engine = VoiceIdentityEngine()
    monkeypatch.setattr(engine, '_decode_audio', lambda *args: np.ones(48000, dtype=np.float32) * .1)
    monkeypatch.setattr(voice_segmentation.engine, 'analyze', lambda samples: {
        'speech_seconds': 3, 'overlap_seconds': .5, 'multiple_speakers': True})
    monkeypatch.setattr(engine, '_get_session', lambda: pytest.fail('Mixed voices reached the identity model'))
    with pytest.raises(VoiceIdentityError, match='Mais de uma voz'):
        engine.embed(b'audio')


def test_missing_model_does_not_download(tmp_path):
    with pytest.raises(ValueError, match='Prepare novamente'):
        VoiceSegmentationEngine(tmp_path / 'missing.onnx').analyze(np.zeros(32000))


def test_segments_preserve_sequential_boundaries_without_overlapping_windows():
    engine = VoiceSegmentationEngine()
    engine._session = Session([1] * 200 + [2] * 389)
    result = engine.analyze(np.ones(240000, dtype=np.float32))
    parts = result['segments']
    assert parts[0]['local_speaker'] != parts[1]['local_speaker']
    assert abs(parts[0]['end'] - 200 * 270 / 16000) < .001
    assert all(a['end'] <= b['start'] for a, b in zip(parts, parts[1:]))
    assert all(0 <= part['start'] < part['end'] <= 15 for part in parts)
