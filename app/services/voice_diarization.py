"""Identify sequential speakers without assigning one person's access to a group."""
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
import wave

from app.services import identity
from app.services.voice_identity import MIN_AUDIO_SECONDS
from app.services.voice_segmentation import engine as segmentation


def identify_turn(raw, content_type):
    profiles = identity._read().get('profiles', [])
    if not any(p.get('voice_embeddings') for p in profiles):
        return {'ok': True, 'enabled': False}
    engine = identity.voice_identity_engine
    try:
        samples = engine._decode_audio(raw, content_type)
        activity = segmentation.analyze(samples)
        if not activity['multiple_speakers'] and len(samples) <= 160000:
            short = len(samples) < 16000 * MIN_AUDIO_SECONDS
            vector = engine.embed_samples(samples, activity=activity, short_turn=short)
            result = identity._match_voice(vector, profiles)
            if short:
                # A brief match is an observation only, even at high similarity.
                candidate = result['profile'] if not result['requires_confirmation'] else None
                result.update(profile=None, matched=False, requires_confirmation=True, reason='short_turn',
                              possible_speaker=candidate['name'] if candidate else None)
            return {**result, 'enabled': True}
        spans = []
        for part in activity['segments']:
            # A breathing pause should not turn one local speaker into tiny, unusable samples.
            if spans and spans[-1]['local_speaker'] == part['local_speaker'] and spans[-1]['overlap'] == part['overlap'] and part['start'] - spans[-1]['end'] < 1.0:
                spans[-1]['end'] = part['end']
            else:
                spans.append(part.copy())
        if len(spans) > 24:
            return {'ok': True, 'enabled': True, 'matched': False, 'requires_confirmation': True,
                    'reason': 'too_many_speaker_changes'}
        turns = []
        for span in spans:
            result = {'matched': False, 'requires_confirmation': True}
            if not span['overlap']:
                try:
                    clip = samples[int(span['start'] * 16000):int(span['end'] * 16000)]
                    vector = engine.embed_samples(clip, activity={'speech_seconds': len(clip) / 16000,
                                                  'multiple_speakers': False, 'overlap_seconds': 0})
                    result = identity._match_voice(vector, profiles)
                except ValueError:
                    pass  # Short/unclear turns remain unknown, never borrowed from a neighbour.
            known = result.get('matched') and not result.get('requires_confirmation')
            person = result.get('profile') if known else None
            turn = {'start': round(span['start'], 3), 'end': round(span['end'], 3),
                    'speaker_name': person.get('name') if person else None,
                    'profile_id': person.get('id') if person else None,
                    'identity_revision': person.get('identity_revision', 0) if person else 0,
                    'confidence': result.get('confidence', 0), 'overlap': span['overlap'],
                    'speaker_state': 'recognized' if known else 'overlap' if span['overlap'] else 'unknown'}
            if turns and person and turns[-1]['profile_id'] == person['id'] and turn['start'] - turns[-1]['end'] < .3:
                turns[-1]['end'] = turn['end']
                turns[-1]['confidence'] = min(turns[-1]['confidence'], turn['confidence'])
            else:
                turns.append(turn)
        ids = {t['profile_id'] for t in turns}
        if turns and len(ids) == 1 and None not in ids and not activity['multiple_speakers']:
            person = next(p for p in profiles if p['id'] in ids)
            return {'ok': True, 'enabled': True, 'matched': True, 'requires_confirmation': False,
                    'profile': identity.IdentityService._public(person), 'confidence': min(t['confidence'] for t in turns)}
        return {'ok': True, 'enabled': True, 'matched': False, 'requires_confirmation': True,
                'multiple_speakers': True, 'reason': 'multiple_or_uncertain_speakers', 'segments': turns}
    except (ValueError, OSError) as error:
        return {'ok': False, 'enabled': True, 'matched': False, 'requires_confirmation': True, 'error': str(error)}


def transcribe_segments(speaker, raw, content_type, transcribe):
    """Extra STT is only needed when more than one speaker was detected."""
    if not speaker.get('segments'):
        return
    import numpy as np
    samples = identity.voice_identity_engine._decode_audio(raw, content_type)
    def transcribe_part(part):
        if part.get('overlap'):
            part['text'] = ''; return
        clip = samples[int(part['start'] * 16000):int(part['end'] * 16000)]
        output = BytesIO()
        with wave.open(output, 'wb') as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000)
            wav.writeframes((np.clip(clip, -1, 1) * 32767).astype('<i2').tobytes())
        try:
            result = transcribe(output.getvalue(), suffix='.wav')
            part['text'] = str(result.get('text') or '')[:4000] if result.get('ok') else ''
        except Exception:
            part['text'] = ''
    # Keep order in the response while avoiding serial STT latency for two speakers.
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix='speaker-stt') as pool:
        list(pool.map(transcribe_part, speaker['segments']))
