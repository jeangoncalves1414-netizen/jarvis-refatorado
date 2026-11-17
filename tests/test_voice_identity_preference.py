from types import SimpleNamespace
from unittest.mock import Mock

from app.ui.panel.api import voice, voice_capture
from app.services import voice_diarization


def test_backend_uses_global_selection_and_can_restore_default():
    from app.storage import runtime_settings
    runtime_settings.set_mic_settings({'device_name': 'USB microphone', 'device_id': 'browser-usb'})
    assert runtime_settings.get_mic_settings()['device_id'] == 'browser-usb'
    assert voice_capture._start_kwargs({'device_name': 'Another microphone'})['device_name'] == 'USB microphone'
    runtime_settings.set_mic_settings({'gain': 2})
    assert runtime_settings.get_mic_settings()['device_name'] == 'USB microphone'
    runtime_settings.set_mic_settings({'device_name': ''})
    assert runtime_settings.get_mic_settings()['device_id'] == ''
    assert voice_capture._start_kwargs({})['device_name'] == ''


def test_speaker_wait_does_not_discard_result_after_old_short_deadline():
    from app.services import turn_speaker, identity_context
    class Pending:
        def result(self, timeout):
            assert timeout >= 1.0
            return {'matched': True, 'profile': {'id': 'jean', 'name': 'Jean'}}
    result = turn_speaker.finish(Pending())
    assert identity_context.consume(result['evidence_token'])['speaker_name'] == 'Jean'


def test_speaker_timeout_never_grants_access():
    from concurrent.futures import Future
    from app.services import turn_speaker, identity_context
    result = turn_speaker.finish(Future(), timeout=0)
    evidence = identity_context.consume(result['evidence_token'])
    assert evidence['reason'] == 'timeout'
    assert evidence['profile_id'] is None


def test_browser_requires_explicit_identification(monkeypatch):
    identify = Mock(return_value={"matched": False})
    monkeypatch.setattr(voice_diarization, "identify_turn", identify)
    pipeline = SimpleNamespace(transcribe_bytes=lambda *a, **k: {"ok": True, "text": "Olá"})
    for enabled in (None, "0", "1"):
        headers = {"Content-Type": "audio/wav"}
        if enabled is not None:
            headers["X-Jarvis-Identify-Speaker"] = enabled
        handler = SimpleNamespace(headers=headers, voice_pipeline=pipeline)
        status, result = voice.handle_voice_post("/api/voice/stt", b"audio", handler)
        assert status == 200
        assert ("speaker" in result) == (enabled == "1")
    assert identify.call_count == 1


def test_backend_preference_changes_during_same_capture(monkeypatch):
    monkeypatch.setattr(voice_capture, "_speaker_identification_enabled", False)
    identify = Mock(return_value={"matched": False})
    monkeypatch.setattr(voice_diarization, "identify_turn", identify)
    handler = SimpleNamespace(client_address=("127.0.0.1", 123),
                              voice_pipeline=SimpleNamespace(transcribe_bytes=lambda *a, **k: {"ok": True}))
    transcribe = voice_capture._transcriber(handler)
    assert "speaker" not in transcribe(b"audio")
    voice_capture.handle_capture_post("/api/voice/capture/identity", b'{"enabled":true}', handler)
    assert "speaker" in transcribe(b"audio")
    voice_capture.handle_capture_post("/api/voice/capture/identity", b'{"enabled":false}', handler)
    assert "speaker" not in transcribe(b"audio")
    assert identify.call_count == 1


def test_disabling_during_inference_discards_result(monkeypatch):
    monkeypatch.setattr(voice_capture, "_speaker_identification_enabled", True)
    def identify(*args):
        voice_capture._speaker_identification_enabled = False
        return {"matched": True, "profile": {"name": "Jean"}}
    monkeypatch.setattr(voice_diarization, "identify_turn", identify)
    handler = SimpleNamespace(voice_pipeline=SimpleNamespace(transcribe_bytes=lambda *a, **k: {"ok": True}))
    assert "speaker" not in voice_capture._transcriber(handler)(b"audio")
