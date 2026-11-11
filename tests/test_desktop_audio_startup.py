import sys
from types import SimpleNamespace


def test_missing_microphone_does_not_prevent_desktop_initialization(monkeypatch):
    from app.ui.desktop import DesktopAPI
    def unavailable():
        raise OSError("No input device")
    monkeypatch.setitem(sys.modules, "speech_recognition", SimpleNamespace(Recognizer=lambda: object(), Microphone=unavailable))
    api = DesktopAPI(SimpleNamespace())
    assert not api._has_sr
    assert api.startRecording().startswith("Erro:")
    assert not api._is_recording


def test_recording_failure_never_claims_started(monkeypatch):
    from app.ui.desktop import DesktopAPI
    def fail(*args):
        raise OSError("Device busy")
    recognizer = SimpleNamespace(listen_in_background=fail)
    monkeypatch.setitem(sys.modules, "speech_recognition", SimpleNamespace(Recognizer=lambda: recognizer, Microphone=lambda: object()))
    api = DesktopAPI(SimpleNamespace())
    assert api.startRecording().startswith("Erro:")
    assert not api._is_recording
