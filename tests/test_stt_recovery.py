from __future__ import annotations

from app.services.voice.stt.engine import STTEngine


def test_oxyy_failure_enters_short_cooldown_and_uses_groq(tmp_path, monkeypatch):
    clip = tmp_path / "voice.webm"; clip.write_bytes(b"audio")
    engine = STTEngine(stt_provider="oxyy", oxyy_api_keys=["test"], groq_api_key="test")
    monkeypatch.setattr(engine, "_transcribe_oxyy", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(engine, "_transcribe_groq", lambda *_args, **_kwargs: "Olá")
    text, error = engine.transcribe_file(str(clip))
    assert text == "Olá" and error is None
    assert engine.last_attempts[0] == {"provider": "oxyy", "outcome": "failed"}
    assert engine.last_attempts[1] == {"provider": "groq", "outcome": "success"}
    calls = []
    monkeypatch.setattr(engine, "_transcribe_oxyy", lambda *_args, **_kwargs: calls.append("oxyy") or "não deveria chamar")
    text, _ = engine.transcribe_file(str(clip))
    assert text == "Olá"
    assert calls == []
    assert engine.last_attempts[0] == {"provider": "oxyy", "outcome": "cooldown"}
