import pytest

from app.services.voice import mic_capture
from app.storage import runtime_settings


def test_paired_phone_selects_its_own_microphone():
    runtime_settings.set_mic_settings({"device_name": "USB no PC", "device_id": "usb"})
    assert not runtime_settings.get_mic_settings(mobile=True)["device_id"]
    runtime_settings.set_mic_settings({"device_name": "Android", "device_id": "phone"}, mobile=True)
    assert runtime_settings.get_mic_settings()["device_id"] == "usb"
    assert runtime_settings.get_mic_settings(mobile=True)["device_id"] == "phone"


def test_selected_name_resolves_to_current_index_not_saved_index(monkeypatch):
    runtime_settings.set_mic_settings({'device_name': 'USB microphone (1234:abcd)', 'device_id': 'opaque-browser-id'})
    monkeypatch.setattr(mic_capture, 'list_devices', lambda: {'devices': [{'index': 7, 'name': 'USB microphone'}]})
    assert mic_capture.resolve_device_index() == 7
    monkeypatch.setattr(mic_capture, 'list_devices', lambda: {'devices': [{'index': 3, 'name': 'USB microphone'}]})
    assert mic_capture.resolve_device_index() == 3
    runtime_settings.set_mic_settings({'device_name': ''})
    assert mic_capture.resolve_device_index() is None


def test_missing_or_ambiguous_device_never_falls_back_to_default():
    with pytest.raises(ValueError, match='indisponível'):
        mic_capture.match_input_device('Headset', [{'index': 0, 'name': 'Laptop mic'}])
    with pytest.raises(ValueError, match='ambíguo'):
        mic_capture.match_input_device('Headset', [{'index': 0, 'name': 'Headset'}, {'index': 2, 'name': 'Headset'}])


def test_windows_truncated_names_only_match_unique_device():
    name = 'Microphone (Very long USB device name)'
    assert mic_capture.match_input_device(name, [{'index': 5, 'name': name[:31]}]) == 5
    with pytest.raises(ValueError):
        mic_capture.match_input_device(name, [{'index': 5, 'name': 'Microphone'}])


def test_capture_reports_missing_device_without_opening_default(monkeypatch):
    monkeypatch.setattr(mic_capture, 'availability', lambda: (True, ''))
    monkeypatch.setattr(mic_capture, 'list_devices', lambda: {'devices': []})
    capture = mic_capture.MicCapture()
    result = capture.start(sensitivity=75, silence_ms=800, gain=1, device_name='Missing', transcribe=lambda _: {})
    assert not result['ok']
    assert not capture.active


@pytest.mark.parametrize('value', [None, 42, [], 'a' * 513])
def test_invalid_device_setting_preserves_previous_selection(value):
    runtime_settings.set_mic_settings({'device_name': 'Headset', 'device_id': 'headset-id'})
    with pytest.raises(ValueError):
        runtime_settings.set_mic_settings({'device_name': value})
    assert runtime_settings.get_mic_settings()['device_name'] == 'Headset'
