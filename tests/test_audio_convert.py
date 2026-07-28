import wave
from pathlib import Path
from unittest.mock import patch

from app.services.voice.audio_convert import convert_to_wav, prepare_audio_for_stt


def _write_minimal_wav(path: Path) -> None:
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)


def test_prepare_wav_passthrough(tmp_path) -> None:
    wav = tmp_path / "sample.wav"
    _write_minimal_wav(wav)
    path, is_temp = prepare_audio_for_stt(str(wav))
    assert path == str(wav)
    assert is_temp is False


def test_convert_webm_calls_ffmpeg(tmp_path) -> None:
    webm = tmp_path / "audio.webm"
    webm.write_bytes(b"\x00" * 32)

    with patch("app.services.voice.audio_convert._ffmpeg_path", return_value="ffmpeg"), patch(
        "app.services.voice.audio_convert.subprocess.run"
    ) as run_mock:
        def fake_run(cmd, **kwargs):
            Path(cmd[-1]).write_bytes(b"RIFF" + b"\x00" * 40)
            return type("R", (), {"returncode": 0})()

        run_mock.side_effect = fake_run
        result = convert_to_wav(str(webm))
        assert result is not None
        assert Path(result).exists()
        run_mock.assert_called_once()
