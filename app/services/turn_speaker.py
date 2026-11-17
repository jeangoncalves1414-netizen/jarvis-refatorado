"""Overlap local speaker inference with transcription, with bounded capacity."""
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import BoundedSemaphore, Lock
import time

from app.services import voice_diarization
from app.services.identity_context import issue

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="speaker")
_slot = BoundedSemaphore(1)
_warming = Lock()


def start(raw, content_type):
    if not _slot.acquire(blocking=False):
        return None
    try:
        future = _pool.submit(voice_diarization.identify_turn, raw, content_type)
    except RuntimeError:
        _slot.release()
        return None
    future.add_done_callback(lambda _: _slot.release())
    return future


def warmup():
    """Load the local models while capture starts, without opening a microphone."""
    from app.services.identity import _read
    if not any(p.get('voice_embeddings') for p in _read().get('profiles', [])):
        return
    if not _warming.acquire(blocking=False):
        return
    def load():
        try:
            from app.services.identity import voice_identity_engine
            from app.services.voice_segmentation import engine
            if voice_identity_engine.status()['ready']:
                engine._get_session()
                voice_identity_engine._get_session()
        finally:
            _warming.release()
    try:
        _pool.submit(load)
    except RuntimeError:
        _warming.release()


def finish(future, timeout=2.0, *, raw=None, content_type='audio/wav', transcribe=None, transcript=''):
    started = time.monotonic()
    try:
        speaker = future.result(timeout=timeout).copy() if future is not None else {"enabled": True, "reason": "busy"}
    except TimeoutError:
        speaker = {"enabled": True, "reason": "timeout"}
    except Exception:
        speaker = {"enabled": True, "reason": "unavailable"}
    from app.core.diagnostics import record
    record('voice.identity', 'turn_identified' if speaker.get('matched') and not speaker.get('requires_confirmation') else 'turn_unknown',
           'INFO', reason=speaker.get('reason'), error=speaker.get('error'), confidence=speaker.get('confidence'),
           wait_ms=round((time.monotonic() - started) * 1000))
    if raw is not None and transcribe and speaker.get('segments'):
        try:
            voice_diarization.transcribe_segments(speaker, raw, content_type, transcribe)
        except Exception:
            for part in speaker['segments']:
                part['text'] = ''
    speaker['text'] = transcript[:8000]
    speaker["evidence_token"] = issue(speaker)
    return speaker
