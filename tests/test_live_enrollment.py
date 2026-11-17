import pytest

from app.services import identity, live_enrollment


@pytest.fixture(autouse=True)
def isolated_enrollment(monkeypatch):
    monkeypatch.setattr(live_enrollment, '_pending', {})


@pytest.fixture
def introduction(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "IDENTITY_FILE", tmp_path / "profiles.json")
    identity.IdentityService.enroll_admin("Jean", "password123")
    monkeypatch.setattr(identity.voice_identity_engine, "embed", lambda *args: [1., 0.])
    return {"name": "Ana", "admin_password": "password123", "consent": True,
            "audio": "data:audio/wav;base64,AA==", "images": ["data:image/jpeg;base64,AA=="] * 3}


def test_live_introduction_commits_all_references_together(introduction, monkeypatch):
    poses = iter([0., .2, -.18])
    monkeypatch.setattr(live_enrollment.faces, "extract",
                        lambda raw: [{"embedding": [1., 0.], "pose": next(poses)}])
    profile = live_enrollment.enroll(introduction)["profile"]
    assert (profile["name"], profile["face_samples"], profile["voice_samples"]) == ("Ana", 3, 1)


def test_repeated_frame_does_not_create_partial_profile(introduction, monkeypatch):
    monkeypatch.setattr(live_enrollment.faces, "extract", lambda raw: [{"embedding": [1., 0.], "pose": 0.}])
    with pytest.raises(ValueError, match="três|cada lado"):
        live_enrollment.enroll(introduction)
    assert len(identity.IdentityService.status()["profiles"]) == 1


def test_absent_camera_allows_voice_enrollment(introduction):
    introduction["images"] = []
    assert live_enrollment.enroll(introduction)["profile"]["face_samples"] == 0
    with pytest.raises(ValueError, match="Já existe"):
        live_enrollment.enroll(introduction)


def test_guided_readings_keep_three_consistent_references(introduction, monkeypatch):
    ticket = live_enrollment.authorize(introduction)['ticket']
    payload = {**introduction, 'ticket': ticket, 'images': []}
    for index, phrase in enumerate(live_enrollment.VOICE_READINGS):
        monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *_: phrase)
        if index == 1:
            with pytest.raises(ValueError, match='leitura'):
                live_enrollment.enroll(payload)
            with monkeypatch.context() as different:
                different.setattr(identity.voice_identity_engine, 'embed', lambda *_: [-1., 0.])
                with pytest.raises(ValueError, match='voz ficou diferente'):
                    live_enrollment.validate_voice({**payload, 'sample_index': index})
        for _ in range(2):  # A retry after a lost reply must not add a second reference.
            result = live_enrollment.validate_voice({**payload, 'sample_index': index})
            assert result.get('next_phrase') == next(iter(live_enrollment.VOICE_READINGS[index+1:]), None)
    assert live_enrollment.enroll(payload)['profile']['voice_samples'] == 3


def test_face_only_requires_three_positions_and_no_voice_model(introduction, monkeypatch):
    ticket = live_enrollment.authorize(introduction)['ticket']
    payload = {'ticket': ticket, 'consent': True, 'face_consent': True, 'modality': 'face', 'images': []}
    with pytest.raises(ValueError, match='três'):
        live_enrollment.enroll(payload)
    monkeypatch.setattr(identity.voice_identity_engine, 'embed', lambda *args: pytest.fail('Face-only requested voice'))
    poses = iter([0., .2, -.2])
    monkeypatch.setattr(live_enrollment.faces, 'extract', lambda _: [{'embedding': [1., 0.], 'pose': next(poses)}])
    result = live_enrollment.enroll({**payload, 'images': introduction['images']})
    assert result['profile']['face_samples'] == 3
    assert result['profile']['voice_samples'] == 0
    assert result['profile']['role'] == 'user'


def test_both_never_silently_saves_only_one_modality(introduction):
    ticket = live_enrollment.authorize(introduction)['ticket']
    live_enrollment._pending[ticket]['voice'] = [1., 0.]
    with pytest.raises(ValueError, match='três'):
        live_enrollment.enroll({'ticket': ticket, 'consent': True, 'modality': 'both', 'images': []})


def test_voice_failure_does_not_create_profile(introduction, monkeypatch):
    introduction["images"] = []
    def reject(*args):
        raise ValueError("Mais de uma voz")
    monkeypatch.setattr(identity.voice_identity_engine, "embed", reject)
    with pytest.raises(ValueError, match="Mais de uma voz"):
        live_enrollment.enroll(introduction)
    assert len(identity.IdentityService.status()["profiles"]) == 1

def test_guided_enrollment_requires_valid_reading_before_commit(introduction, monkeypatch):
    ticket = live_enrollment.authorize(introduction)['ticket']
    payload = {'ticket': ticket, 'consent': True, 'images': []}
    with pytest.raises(ValueError, match='leitura'):
        live_enrollment.enroll(payload)
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: 'texto diferente')
    with pytest.raises(ValueError, match='mínimo é 80%'):
        live_enrollment.validate_voice({**introduction, 'ticket': ticket})
    assert len(identity.IdentityService.status()['profiles']) == 1
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: live_enrollment.READING)
    live_enrollment.validate_voice({**introduction, 'ticket': ticket})
    result = live_enrollment.enroll(payload)
    assert result['profile']['voice_samples'] == 1
    assert result['profile']['permissions'] == []
    with pytest.raises(ValueError, match='expirou'):
        live_enrollment.enroll(payload)


def test_guided_authorization_and_separate_consent(introduction, monkeypatch):
    assert live_enrollment.authorize({**introduction, 'admin_password': '', 'profile_id': 'admin'})['ok']
    ticket = live_enrollment.authorize(introduction)['ticket']
    with pytest.raises(ValueError, match='autorizar'):
        live_enrollment.validate_voice({**introduction, 'ticket': ticket, 'consent': False})
    with pytest.raises(ValueError, match='separadamente'):
        live_enrollment.enroll({**introduction, 'ticket': ticket})
    live_enrollment.cancel(ticket)
    with pytest.raises(ValueError, match='expirou'):
        live_enrollment.validate_voice({**introduction, 'ticket': ticket})


@pytest.mark.parametrize('heard, accepted', [
    ('dez nove oito sete seis cinco quatro três', True),
    ('dez nove oito sete seis cinco quatro', False),
    ('um ' * 20, False),
])
def test_reading_accepts_eighty_percent_in_any_order(introduction, monkeypatch, heard, accepted):
    monkeypatch.setattr(live_enrollment, 'READING', 'um dois três quatro cinco seis sete oito nove dez')
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: heard)
    ticket = live_enrollment.authorize(introduction)['ticket']
    if accepted:
        assert live_enrollment.validate_voice({**introduction, 'ticket': ticket})['coverage'] == .8
    else:
        with pytest.raises(ValueError, match='80%'):
            live_enrollment.validate_voice({**introduction, 'ticket': ticket})
        assert 'voice' not in live_enrollment._pending[ticket]


def test_reading_ignores_case_accents_and_missing_jarvis(introduction, monkeypatch):
    heard = ' '.join(reversed(live_enrollment.READING.replace('Jarvis', '').upper().split()))
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: heard)
    ticket = live_enrollment.authorize(introduction)['ticket']
    assert live_enrollment.validate_voice({**introduction, 'ticket': ticket})['coverage'] > .8
    assert live_enrollment.reading_coverage('Referência VOZ Jarvis voz', 'jarvis referencia voz') == .75


def test_reading_preserves_completed_phrases_across_pauses(monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from app.services.voice import wake_word
    class Reader:
        def __init__(self, *args): self.count = 0
        def AcceptWaveform(self, pcm):
            assert len(pcm) <= 8000
            self.count += 1
            return self.count == 1
        def Result(self): return json.dumps({'text': 'eu autorizo o jarvis'})
        def FinalResult(self): return json.dumps({'text': 'a reconhecer minha voz'})
    monkeypatch.setattr(wake_word, '_get_model', lambda **kw: object())
    monkeypatch.setitem(sys.modules, 'vosk', SimpleNamespace(KaldiRecognizer=Reader))
    assert live_enrollment.transcribe_pcm(bytes(16000)) == 'eu autorizo o jarvis a reconhecer minha voz'


def test_guided_authorization_accepts_admin_voice(introduction):
    from app.services.identity_context import issue
    admin = identity.IdentityService.status()['profiles'][0]
    proof = issue({'matched': True, 'profile': admin})
    assert live_enrollment.authorize({'name': 'Jamille', 'identity_token': proof})['ok']
    assert live_enrollment.authorize({'name': 'Maria'})['ok']


@pytest.fixture
def recadastro(introduction, monkeypatch):
    from app.services.app_lock import app_lock
    app_lock.perform({'action': 'setup', 'password': 'unlock-password'})
    data = identity._read()
    admin = data['profiles'][0]
    admin.update(voice_embeddings=[[1., 0.]], face_embeddings_sface=[[1., 0.]],
                 voice_vectors=[[0., 1.]], face_vectors=[[0., 1.]])
    identity._write(data)
    photo = identity.FACE_DIR / f"{admin['id']}.jpg"
    photo.write_bytes(b'legacy reference')
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: live_enrollment.READING)
    return {'purpose': 'admin_reenroll', 'admin_password': 'unlock-password'}, admin, photo


def test_admin_reenroll_requires_password_even_with_recognized_voice(recadastro):
    from app.services.identity_context import issue
    payload, admin, _ = recadastro
    before = identity.IDENTITY_FILE.read_bytes()
    token = issue({'matched': True, 'profile': identity.IdentityService._public(admin)})
    with pytest.raises(ValueError, match='verificar'):
        live_enrollment.authorize({**payload, 'admin_password': '', 'identity_token': token})
    assert identity.IDENTITY_FILE.read_bytes() == before
    assert not live_enrollment._pending


def test_admin_wrong_password_is_rate_limited(recadastro):
    payload, _, _ = recadastro
    for _ in range(5):
        with pytest.raises(ValueError, match='verificar'):
            live_enrollment.authorize({**payload, 'admin_password': 'wrong'})
    with pytest.raises(ValueError, match='30 segundos'):
        live_enrollment.authorize(payload)


def test_cancelled_or_incomplete_admin_reenrollment_preserves_profile(recadastro):
    payload, _, photo = recadastro
    before = identity.IDENTITY_FILE.read_bytes()
    ticket = live_enrollment.authorize(payload)['ticket']
    with pytest.raises(ValueError, match='leitura'):
        live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': []})
    live_enrollment.cancel(ticket)
    assert identity.IDENTITY_FILE.read_bytes() == before and photo.exists()
    with pytest.raises(ValueError, match='expirou'):
        live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': []})


@pytest.mark.parametrize('with_face', [False, True])
def test_admin_reenroll_replaces_samples_and_revokes_old_evidence(recadastro, introduction, monkeypatch, with_face):
    from app.services import identity_context, identity_access
    payload, admin, photo = recadastro
    public = identity.IdentityService._public(admin)
    stale = identity_context.consume(identity_context.issue({'matched': True, 'profile': public}))
    other = identity.IdentityService.enroll_profile('Jamille', 'user', 'unlock-password')['profile']
    other_before = identity._read()['profiles'][1]
    ticket = live_enrollment.authorize(payload)['ticket']
    second_ticket = live_enrollment.authorize(payload)['ticket']
    live_enrollment.validate_voice({**introduction, 'ticket': ticket})
    poses = iter([0., .2, -.18])
    monkeypatch.setattr(live_enrollment.faces, 'extract', lambda raw: [{'embedding': [1., 0.], 'pose': next(poses)}])
    result = live_enrollment.enroll({'ticket': ticket, 'consent': True, 'face_consent': with_face,
                                     'images': introduction['images'] if with_face else []})
    updated = identity._read()['profiles'][0]
    assert result['profile']['id'] == admin['id'] and updated['role'] == 'admin'
    assert updated['name'] == admin['name'] and updated['password'] == admin['password']
    assert updated['created_at'] == admin['created_at']
    assert updated['voice_embeddings'] == [[1., 0.]]
    assert len(updated['face_embeddings_sface']) == (3 if with_face else 0)
    assert updated['voice_vectors'] == updated['face_vectors'] == []
    assert identity._read()['profiles'][1] == other_before and other['role'] == 'user'
    assert not photo.exists()
    assert not identity_access.access(stale)[0]
    fresh = identity_context.consume(identity_context.issue({'matched': True, 'profile': result['profile']}))
    assert identity_access.access(fresh)[0]
    with pytest.raises(ValueError, match='revogada'):
        live_enrollment.enroll({'ticket': second_ticket, 'consent': True, 'images': []})


def test_admin_write_failure_keeps_old_samples_and_photo(recadastro, introduction, monkeypatch):
    payload, _, photo = recadastro
    before = identity.IDENTITY_FILE.read_bytes()
    ticket = live_enrollment.authorize(payload)['ticket']
    live_enrollment.validate_voice({**introduction, 'ticket': ticket})
    def fail_write(data):
        raise OSError('disk unavailable')
    monkeypatch.setattr(identity, '_write', fail_write)
    with pytest.raises(OSError):
        live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': []})
    assert identity.IDENTITY_FILE.read_bytes() == before and photo.exists()


def test_user_ticket_cannot_be_promoted_to_admin(introduction, monkeypatch):
    ticket = live_enrollment.authorize(introduction)['ticket']
    monkeypatch.setattr(live_enrollment, 'transcribe_reading', lambda *args: live_enrollment.READING)
    live_enrollment.validate_voice({**introduction, 'ticket': ticket})
    result = live_enrollment.enroll({'ticket': ticket, 'consent': True, 'images': [], 'role': 'admin', 'purpose': 'admin_reenroll'})
    assert result['profile']['role'] == 'user'
