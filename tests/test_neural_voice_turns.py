from concurrent.futures import Future
from types import SimpleNamespace
import time

import numpy as np

from app.services.voice.mic_capture import CHUNK, MicCapture
from app.services.voice.turn_audio import endpoint_ready


class ImmediateWorker:
    def submit(self, fn, *args):
        result = Future()
        result.set_result(fn(*args))
        return result


class FakeNeural:
    def __init__(self, probabilities):
        self.probabilities = iter(probabilities)

    def speech_probability(self, pcm, *_):
        return 0.95 if pcm[0] else 0.01

    def completion_probability(self, *_):
        return next(self.probabilities, 0.95)


def frames(seconds, speech):
    return [bytes([1 if speech else 0, 0]) * CHUNK] * int(seconds * 16000 / CHUNK)


def run_capture(audio, probabilities):
    capture = MicCapture()
    capture._last_poll = time.monotonic()
    capture._neural = FakeNeural(probabilities)
    capture._active = True
    submitted = []
    capture._submit = lambda *args, **kwargs: submitted.append((args, kwargs))
    iterator = iter(audio)
    source = SimpleNamespace(SAMPLE_RATE=16000, SAMPLE_WIDTH=2,
                             stream=SimpleNamespace(read=lambda _: next(iterator, b"")))
    capture._capture_loop(source, 0.8, lambda _: {}, ImmediateWorker())
    return capture, submitted


def test_hesitation_keeps_audio_until_neural_completion():
    _, submitted = run_capture(frames(1, True) + frames(4, False) + frames(1, True) + frames(2, False), [0.1, 0.95])
    assert len(submitted) == 1
    assert submitted[0][1]["turn_complete"] is True
    assert submitted[0][0][4] > 6  # Both spoken portions and thinking pause retained.


def test_max_segment_is_not_permission_to_answer():
    _, submitted = run_capture(frames(22, True) + frames(2, False), [0.95])
    assert len(submitted) == 2
    assert submitted[0][1]["turn_complete"] is False
    assert submitted[1][1]["turn_complete"] is True


def test_uncertain_model_waits_but_does_not_wait_forever():
    _, submitted = run_capture(frames(1, True) + frames(7, False), [0.1])
    assert not submitted
    _, submitted = run_capture(frames(1, True) + frames(9, False), [0.1])
    assert len(submitted) == 1
    assert not endpoint_ready(4, 0.1)
    assert not endpoint_ready(1, 0.99)
    assert endpoint_ready(1.6, 0.9)
    assert endpoint_ready(8.1, None)


def test_noise_without_voice_does_not_submit():
    _, submitted = run_capture(frames(10, False), [])
    assert not submitted


def test_transcription_from_stopped_call_is_discarded():
    capture = MicCapture()
    generation = capture._generation
    def transcribe(_):
        capture._generation += 1
        return {"ok": True, "text": "Resposta de uma chamada antiga"}
    capture._transcribe("old", np.zeros(16000, dtype=np.int16).tobytes(), 16000, 2, transcribe, generation)
    assert not capture.events()["events"]


def test_prediction_from_previous_pause_cannot_finish_new_speech():
    capture = MicCapture()
    capture._last_poll = time.monotonic()
    capture._neural = FakeNeural([0.1])
    submitted = []
    capture._submit = lambda *args, **kwargs: submitted.append(args)
    delayed = Future()
    class Worker(ImmediateWorker):
        calls = 0
        def submit(self, fn, *args):
            self.calls += 1
            return delayed if self.calls == 1 else super().submit(fn, *args)
    worker = Worker()
    iterator = iter(frames(1, True) + frames(2, False) + frames(1, True) + frames(4, False))
    def read(_):
        frame = next(iterator, b"")
        if frame and frame[0] and worker.calls and not delayed.done():
            delayed.set_result(0.99)
        return frame
    source = SimpleNamespace(SAMPLE_RATE=16000, SAMPLE_WIDTH=2, stream=SimpleNamespace(read=read))
    capture._capture_loop(source, 0.8, lambda _: {}, worker)
    assert not submitted


def test_whisper_features_match_expected_model_shape():
    from app.services.voice.vendor.whisper_features import compute_whisper_log_mel_features
    features = compute_whisper_log_mel_features(np.zeros(128000, dtype=np.float32))
    assert features.shape == (80, 800)
    assert features.dtype == np.float32
    assert np.isfinite(features).all()
