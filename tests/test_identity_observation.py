from app.services.identity_observation import combine


def identified(name, probable=False):
    return {'matched': True, 'profile': {'id': name}, 'requires_confirmation': probable}


def test_visible_jean_does_not_own_sisters_voice():
    result = combine(identified('sister'), [identified('jean')])
    assert result['relation'] == 'different_from_identified_faces'
    assert result['speaker']['profile']['id'] == 'sister'
    assert result['active_speaker_verified'] is False
    assert result['grants_access'] is False


def test_unknown_voice_is_not_assigned_to_visible_person():
    result = combine({'matched': False}, [identified('jean')])
    assert result['relation'] == 'unknown'


def test_probable_voice_does_not_establish_relation():
    assert combine(identified('sister', True), [identified('jean')])['relation'] == 'unknown'


def test_same_identity_does_not_prove_lip_sync():
    result = combine(identified('jean'), [identified('jean')])
    assert result['relation'] == 'speaker_identity_visible'
    assert not result['active_speaker_verified']
