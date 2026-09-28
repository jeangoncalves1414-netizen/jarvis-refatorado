from __future__ import annotations

from io import BytesIO
from unittest.mock import patch

from app.services.voice.tts.providers.fish_audio import FishAudioProvider


class _Response(BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


def test_fish_provider_uses_model_header_and_reference_id():
    provider = FishAudioProvider(
        api_key="fish-test",
        reference_id="voice-test",
        model="s2.1-pro-free",
    )
    with patch(
        "app.services.voice.tts.providers.fish_audio.urlopen",
        return_value=_Response(b"ID3-audio"),
    ) as mocked:
        result = provider.generate("Olá, Jarvis.")

    assert result == b"ID3-audio"
    request = mocked.call_args.args[0]
    assert request.get_header("Authorization") == "Bearer fish-test"
    assert request.get_header("Model") == "s2.1-pro-free"
    assert b'"reference_id": "voice-test"' in request.data


def test_fish_provider_is_unavailable_without_key():
    provider = FishAudioProvider(api_key="", reference_id="voice-test")
    assert not provider.is_available()
    assert provider.generate("teste") is None
