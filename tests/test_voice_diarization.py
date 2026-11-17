import numpy as np
import pytest

from app.services import identity, identity_context, voice_diarization as diarization


@pytest.fixture
def conversation(monkeypatch):
    identity._write({'profiles': [
        {'id': 'jean', 'name': 'Jean', 'role': 'admin', 'voice_embeddings': [[1., 0.]]},
        {'id': 'ana', 'name': 'Ana', 'role': 'user', 'voice_embeddings': [[0., 1.]]},
    ]})
    samples = np.concatenate([np.ones(48000), -np.ones(48000)]).astype('float32') * .1
    monkeypatch.setattr(identity.voice_identity_engine, '_decode_audio', lambda *args: samples)
    monkeypatch.setattr(identity.voice_identity_engine, 'embed_samples',
                        lambda samples, **kwargs: [1., 0.] if samples.mean() > 0 else [0., 1.])
    activity = {'speech_seconds': 6, 'overlap_seconds': 0, 'multiple_speakers': True,
                'segments': [{'start': 0, 'end': 3, 'local_speaker': '0:0', 'overlap': False},
                             {'start': 3, 'end': 6, 'local_speaker': '0:1', 'overlap': False}]}
    monkeypatch.setattr(diarization.segmentation, 'analyze', lambda _: activity)
    return activity


def test_sequential_people_are_named_but_group_never_borrows_admin_access(conversation):
    result = diarization.identify_turn(b'audio', 'audio/wav')
    assert [part['speaker_name'] for part in result['segments']] == ['Jean', 'Ana']
    assert not result['matched'] and result['requires_confirmation']
    evidence = identity_context.consume(identity_context.issue(result))
    assert evidence['profile_id'] is None
    assert evidence['speaker_state'] == 'unknown'
    assert [s['speaker_name'] for s in evidence['speaker_segments']] == ['Jean', 'Ana']


def test_overlap_never_receives_one_persons_identity(conversation):
    conversation['segments'][1]['overlap'] = True
    result = diarization.identify_turn(b'audio', 'audio/wav')
    assert result['segments'][1]['speaker_name'] is None
    assert result['segments'][1]['speaker_state'] == 'overlap'


def test_transcripts_belong_to_their_audio_slices(conversation):
    import wave
    from io import BytesIO
    result = diarization.identify_turn(b'audio', 'audio/wav')
    def transcribe(raw, suffix):
        assert suffix == '.wav'
        with wave.open(BytesIO(raw), 'rb') as wav:
            clip = np.frombuffer(wav.readframes(wav.getnframes()), dtype='<i2')
        return {'ok': True, 'text': 'Primeira fala' if clip.mean() > 0 else 'Segunda fala'}
    diarization.transcribe_segments(result, b'audio', 'audio/wav', transcribe)
    assert [(s['speaker_name'], s['text']) for s in result['segments']] == [('Jean', 'Primeira fala'), ('Ana', 'Segunda fala')]


def test_single_voice_does_not_add_transcription_calls(conversation):
    conversation['multiple_speakers'] = False
    result = diarization.identify_turn(b'audio', 'audio/wav')
    assert result['matched']
    diarization.transcribe_segments(result, b'audio', 'audio/wav', lambda *args, **kwargs: pytest.fail('Extra STT'))


def test_short_single_voice_can_suggest_a_name_without_unlocking_access(conversation, monkeypatch):
    conversation['multiple_speakers'] = False
    monkeypatch.setattr(identity.voice_identity_engine, '_decode_audio', lambda *args: np.full(20000, .1))
    result = diarization.identify_turn(b'audio', 'audio/wav')
    evidence = identity_context.consume(identity_context.issue(result))
    assert result['requires_confirmation'] and not result['matched']
    assert evidence['profile_id'] is None and evidence['speaker_state'] == 'unknown'
    ctx = identity_context.current.set(evidence)
    try:
        assert 'parece ser Jean' in identity_context.direct_answer('Quem está falando agora?')
    finally:
        identity_context.current.reset(ctx)


def test_long_speech_keeps_breathing_pauses_with_the_same_local_speaker(conversation, monkeypatch):
    conversation.update(multiple_speakers=False, segments=[
        {'start': 0, 'end': 1.5, 'local_speaker': '0:0', 'overlap': False},
        {'start': 1.9, 'end': 4, 'local_speaker': '0:0', 'overlap': False},
    ])
    monkeypatch.setattr(identity.voice_identity_engine, '_decode_audio', lambda *args: np.full(176000, .1, dtype='float32'))
    clips = []
    def embed(clip, **kwargs):
        clips.append(len(clip))
        if len(clip) < 32000: raise ValueError('too short')
        return [1., 0.]
    monkeypatch.setattr(identity.voice_identity_engine, 'embed_samples', embed)
    result = diarization.identify_turn(b'audio', 'audio/wav')
    assert result['matched'] and result['profile']['id'] == 'jean'
    assert clips == [64000]


@pytest.mark.parametrize('second', ['same', 'other', 'missing', 'probable'])
def test_buffered_turns_preserve_attribution_and_fail_closed(second):
    def token(name, probable=False):
        return identity_context.issue({'matched': True, 'requires_confirmation': probable,
                                       'profile': {'id': name, 'name': name}, 'text': f'fala de {name}'})
    first = token('Jean')
    other = token('Jean') if second == 'same' else token('Ana', second == 'probable') if second != 'missing' else ''
    merged = identity_context.merge_turns([first, other])
    evidence = identity_context.consume(merged['evidence_token'])
    assert (evidence['speaker_state'] == 'recognized') is (second == 'same')
    assert len(evidence['speaker_segments']) == 2
    assert evidence['speaker_segments'][0]['text'] == 'fala de Jean'
    assert identity_context.consume(first) is None


def test_diarized_observation_uses_measured_names_and_text(conversation):
    result = diarization.identify_turn(b'audio', 'audio/wav')
    result['segments'][0]['text'] = 'Olá Jarvis'
    ctx = identity_context.current.set(identity_context.consume(identity_context.issue(result)))
    try:
        answer = identity_context.direct_answer('Quem falou?')
        assert 'Jean: “Olá Jarvis”' in answer and 'Ana' in answer
    finally:
        identity_context.current.reset(ctx)
