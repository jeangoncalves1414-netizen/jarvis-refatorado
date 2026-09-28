"""
Unit tests for the 4 newly extracted advanced features:
1. TurnDetectorEngine
2. VoiceEmotionAnalyzer
3. MultiDeobfuscatorEngine
4. SandboxRunner
5. VoiceCallEngine Integration
"""
import struct
import pytest
from app.services.turn_detector import TurnDetectorEngine, TurnDecision
from app.services.voice_emotion import VoiceEmotionAnalyzer, EmotionalState
from app.services.multi_deobfuscator import MultiDeobfuscatorEngine
from app.services.sandbox_runner import SandboxRunner
from app.services.voice_call import VoiceCallEngine


# ── 1. TurnDetectorEngine Tests ──────────────────────────────────────────────

def test_turn_detector_finished_sentence():
    detector = TurnDetectorEngine()
    res = detector.evaluate("Qual é o clima de hoje em São Paulo?", pause_duration_s=0.5)
    assert res.decision == TurnDecision.FINISHED
    assert res.is_question


def test_turn_detector_unfinished_sentence():
    detector = TurnDetectorEngine()
    res = detector.evaluate("Eu estava pensando que se a gente", pause_duration_s=0.5)
    assert res.decision == TurnDecision.UNFINISHED


def test_turn_detector_hesitation():
    detector = TurnDetectorEngine()
    res = detector.evaluate("Eu quero ir lá tipo", pause_duration_s=0.8)
    assert res.decision == TurnDecision.WAIT


def test_turn_detector_long_pause_override():
    detector = TurnDetectorEngine()
    res = detector.evaluate("Bom dia Jarvis", pause_duration_s=2.0)
    assert res.decision == TurnDecision.FINISHED


# ── 2. VoiceEmotionAnalyzer Tests ────────────────────────────────────────────

def test_voice_emotion_analyzer_neutral():
    analyzer = VoiceEmotionAnalyzer()
    # Generates 10 silent/low PCM frames
    pcm = struct.pack("<160h", *[50] * 160)
    for _ in range(10):
        analyzer.feed_frame(pcm)

    reading = analyzer.get_current_reading()
    assert reading.state in (EmotionalState.NEUTRAL, EmotionalState.CALM, EmotionalState.FATIGUED)
    assert "state_label" in reading.to_dict()


def test_voice_emotion_analyzer_frustrated():
    analyzer = VoiceEmotionAnalyzer()
    import random
    for i in range(20):
        # Varying loud PCM frames
        mult = 15000 if i % 2 == 0 else 5000
        loud_pcm = struct.pack("<160h", *[random.randint(-mult, mult) for _ in range(160)])
        analyzer.feed_frame(loud_pcm)

    reading = analyzer.get_current_reading(words_spoken=20, duration_s=4.0)
    assert reading.state in (EmotionalState.FRUSTRATED, EmotionalState.STRESSED, EmotionalState.EXCITED, EmotionalState.NEUTRAL)
    assert reading.speech_rate > 0.0


# ── 3. MultiDeobfuscatorEngine Tests ─────────────────────────────────────────

def test_multi_deobfuscator_js_hex():
    engine = MultiDeobfuscatorEngine()
    obfuscated_js = 'var _0x1 = "\\x68\\x65\\x6c\\x6c\\x6f";'
    res = engine.deobfuscate_js(obfuscated_js)
    assert res.ok
    assert "hello" in res.output
    assert "hex_escape_decode" in res.passes_applied


def test_multi_deobfuscator_python_b64():
    engine = MultiDeobfuscatorEngine()
    import base64
    payload = base64.b64encode(b"print('Hello Jarvis')").decode()
    py_code = f"import base64\nexec(base64.b64decode('{payload}'))"
    res = engine.deobfuscate_python(py_code)
    assert res.ok
    assert "Hello Jarvis" in res.output
    assert "base64_decode" in res.passes_applied


def test_multi_deobfuscator_binary():
    engine = MultiDeobfuscatorEngine()
    # Simulate a tiny PE header with an embedded URL
    fake_pe = b"MZ" + b"\x00" * 0x3A + struct.pack("<I", 0x40) + b"\x00" * 4 + b"PE\x00\x00" + b"\x64\x86" + b"\x00" * 20 + b"http://malicious-domain.com/c2"
    res = engine.analyze_binary(fake_pe)
    assert res.ok
    assert "PE Header detectado" in res.output
    assert "http://malicious-domain.com/c2" in res.output


# ── 4. SandboxRunner Tests ───────────────────────────────────────────────────

def test_sandbox_runner_safe_command():
    runner = SandboxRunner(default_timeout_s=5.0)
    res = runner.run("echo Jarvis Sandbox Test")
    assert res.ok
    assert "Jarvis Sandbox Test" in res.stdout


def test_sandbox_runner_denylist_blocking():
    runner = SandboxRunner(default_timeout_s=5.0)
    res = runner.run("rm -rf /")
    assert not res.ok
    assert res.blocked
    assert "bloqueado" in res.stderr.lower()


def test_sandbox_runner_python_code():
    runner = SandboxRunner(default_timeout_s=5.0)
    res = runner.run_python_code("print(2 + 2)")
    assert res.ok
    assert "4" in res.stdout.strip()


# ── 5. VoiceCallEngine Integration Tests ─────────────────────────────────────

def test_voice_call_engine_integration():
    engine = VoiceCallEngine()
    session = engine.start_call("test_session_123")
    assert session.session_id == "test_session_123"

    # Evaluate turn
    turn_res = engine.evaluate_turn("test_session_123", "Qual a previsão do tempo?", pause_s=0.5)
    assert turn_res["ok"]
    assert turn_res["decision"] == "finished"

    # Get emotion
    emo_res = engine.get_emotion("test_session_123")
    assert emo_res["ok"]
    assert "state" in emo_res

    # End call
    end_res = engine.end_call("test_session_123")
    assert end_res["ok"]
    assert end_res["duration_sec"] >= 0.0
