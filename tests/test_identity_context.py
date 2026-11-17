from app.services import identity_context as context


def test_direct_voice_question_keeps_offscreen_speaker_separate():
    state = context.current.set({'speaker_name': 'Ana', 'visible_people': ['Jean']})
    try:
        question = 'Quem falou e quem apareceu na câmera neste turno? Use apenas a identificação local disponível e responda em uma frase.'
        assert context.direct_answer(question) == 'A voz identificada foi a de Ana. Vi Jean na câmera.'
        assert context.direct_answer('Quem falou ontem sobre a câmera?') is None
    finally:
        context.current.reset(state)


def test_evidence_is_one_use_and_probable_identity_stays_unknown():
    token = context.issue({'matched': True, 'requires_confirmation': True, 'profile': {'name': 'Jean'}})
    assert context.consume(token) == {'speaker_name': None, 'speaker_state': 'unknown', 'profile_id': None, 'identity_revision': 0, 'method': 'voice'}
    assert context.consume(token) is None


def test_expired_evidence_is_not_reused(monkeypatch):
    token = context.issue({'matched': True, 'profile': {'name': 'Jean'}})
    now = context.time.monotonic()
    monkeypatch.setattr(context.time, 'monotonic', lambda: now + 61)
    assert context.consume(token) is None


def test_probable_speaker_answers_actual_voice_questions_without_granting_access():
    from app.services.identity_access import recognized_profile
    evidence = context.consume(context.issue({'matched': True, 'reason': 'matched', 'requires_confirmation': True,
                                              'profile': {'id': 'admin', 'name': 'Jean'}}))
    assert recognized_profile(evidence) is None and evidence['profile_id'] is None
    state = context.current.set(evidence)
    try:
        for question in ('quem está falando agora Jarvis',
                         'vou falar mais devagar para você identificar você consegue saber quem está falando',
                         'agora você consegue identificar quem está falando'):
            assert 'parece ser Jean' in context.direct_answer(question)
    finally:
        context.current.reset(state)


def test_prompt_keeps_identity_separate_from_permissions():
    token = context.current.set({'speaker_name': 'Irmã', 'speaker_state': 'recognized'})
    try:
        prompt = context.prompt()
        assert 'Irmã' in prompt
        assert 'não autoriza acesso' in prompt
        assert 'Não deduza quem falou pelo rosto' in prompt
    finally:
        context.current.reset(token)
    assert context.prompt() == ''


def test_tracked_turn_receives_evidence_and_clears_it(isolated_lote6_data):
    from app.agent.run_tracking import track_run
    from app.agent.orchestrator import AgentPlan
    observed = []

    @track_run
    def turn(text, origin=None, identity_token=None):
        observed.append(context.current.get())
        return AgentPlan(intent='chat', summary='ok', actions=[])

    token = context.issue({'matched': True, 'profile': {'name': 'Jean'}})
    turn('teste', origin='voice', identity_token=token)
    turn('segunda fala', origin='voice', identity_token=token)
    assert observed[0]['speaker_name'] == 'Jean'
    assert observed[1] is None
    assert context.current.get() is None


def test_camera_preserves_separate_speaker_and_visible_people(monkeypatch):
    from app.services import face_identity, identity
    monkeypatch.setattr(face_identity.engine, 'extract', lambda _: [{'embedding': [1., 0.]}])
    monkeypatch.setattr(identity, '_read', lambda: {'profiles': [{'id': 'jean', 'name': 'Jean', 'face_embeddings_sface': [[1., 0.]]}]})
    token = context.issue({'matched': True, 'profile': {'name': 'Irmã'}})
    result = context.attach_camera(token, b'frame')
    evidence = context.consume(result['evidence_token'])
    assert evidence['speaker_name'] == 'Irmã'
    assert evidence['visible_people'] == ['Jean']
    assert evidence['active_speaker_verified'] is False
    assert context.consume(token) is None


def test_visible_face_never_fills_missing_voice(monkeypatch):
    from app.services import face_identity, identity
    monkeypatch.setattr(face_identity.engine, 'extract', lambda _: [{'embedding': [1., 0.]}])
    monkeypatch.setattr(identity, '_read', lambda: {'profiles': [{'id': 'jean', 'name': 'Jean', 'face_embeddings_sface': [[1., 0.]]}]})
    evidence = context.consume(context.attach_camera(None, b'frame')['evidence_token'])
    assert evidence['speaker_name'] is None
    assert evidence['visible_people'] == ['Jean']
