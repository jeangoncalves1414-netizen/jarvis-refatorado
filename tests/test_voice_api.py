import json
import threading
import urllib.error
import urllib.request
import uuid
from http.server import HTTPServer
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.usefixtures('isolated_lote6_data')

from app.agent.orchestrator import AgentOrchestrator
from app.config import Settings
from app.domain.chat import ChatSession
from app.services.llm import LLMService
from app.services.voice.audio_convert import AudioConversionError, prepare_audio_for_stt
from app.services.voice.pipeline import VoicePipeline
from app.storage.tutor_store import TutorStore
from app.ui.panel.server import PanelHandler


def test_paired_phone_transcribes_without_comparing_speakers():
    from types import SimpleNamespace
    from app.ui.panel.api.voice import handle_voice_post
    pipeline = MagicMock()
    pipeline.transcribe_bytes.return_value = {"ok": True, "text": "bom dia"}
    handler = SimpleNamespace(paired_panel=True, voice_pipeline=pipeline,
                              headers={"X-Jarvis-Identify-Speaker": "1", "Content-Type": "audio/webm"})
    with patch("app.services.turn_speaker.start") as identify:
        assert handle_voice_post("/api/voice/stt", b"sample", handler) == (200, {"ok": True, "text": "bom dia"})
        identify.assert_not_called()


def test_paired_phone_keeps_fish_voice_when_provider_fails():
    from types import SimpleNamespace
    from app.ui.panel.api.voice import handle_voice_post
    pipeline = MagicMock()
    handler = SimpleNamespace(paired_panel=True, voice_pipeline=pipeline, settings=Settings())
    with patch("app.ui.panel.api.voice.FishAudioProvider.from_settings") as provider:
        provider.return_value.generate.return_value = None
        status, result = handle_voice_post("/api/voice/tts", b'{"text":"Bom dia"}', handler)
        assert status == 503 and not result["ok"]
        pipeline.synthesize_bytes.assert_not_called()


def _request(method: str, url: str, data: bytes | None = None, content_type: str = "application/json") -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", content_type)
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


@pytest.fixture()
def panel_http(tmp_path, monkeypatch):
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(sessions_file))
    monkeypatch.setattr("app.storage.session_store.DATA_DIR", str(tmp_path))

    tutor_store = TutorStore(storage_dir=str(tmp_path / f"tutor-{uuid.uuid4().hex}"))
    settings = Settings()
    settings.host = "127.0.0.1"
    settings.port = 0

    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm, tutor_store=tutor_store)
    PanelHandler.orchestrator = orchestrator
    PanelHandler.settings = settings
    PanelHandler.voice_pipeline = MagicMock()

    class _TestPanelHandler(PanelHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.orchestrator = orchestrator
            self.settings = settings
            self.voice_pipeline = PanelHandler.voice_pipeline

    server = HTTPServer(("127.0.0.1", 0), _TestPanelHandler)
    host, port = server.server_address
    # The hardened local control plane validates Host against the configured
    # panel port; the test server receives an ephemeral port after binding.
    settings.port = port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"

    yield base, PanelHandler.voice_pipeline

    server.shutdown()
    thread.join(timeout=2)
    PanelHandler.voice_pipeline = None
    PanelHandler.orchestrator = None


def test_voice_stt_success(panel_http) -> None:
    base, pipeline = panel_http
    pipeline.transcribe_bytes.return_value = {"text": "Olá Jarvis", "ok": True, "error": None}

    status, body = _request("POST", f"{base}/api/voice/stt", b"\x00" * 64, content_type="audio/webm")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is True
    assert data["text"] == "Olá Jarvis"
    pipeline.transcribe_bytes.assert_called_once()
    args, kwargs = pipeline.transcribe_bytes.call_args
    assert kwargs.get("suffix") == ".webm"


def test_voice_stt_empty_body(panel_http) -> None:
    base, pipeline = panel_http
    status, body = _request("POST", f"{base}/api/voice/stt", b"", content_type="audio/webm")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is False
    assert data["error"]
    pipeline.transcribe_bytes.assert_not_called()


def test_voice_stt_conversion_error(panel_http) -> None:
    base, pipeline = panel_http
    pipeline.transcribe_bytes.return_value = {
        "text": "",
        "ok": False,
        "error": "Não foi possível converter o áudio (.webm).",
    }

    status, body = _request("POST", f"{base}/api/voice/stt", b"\x00" * 32, content_type="audio/webm")
    assert status == 200
    data = json.loads(body)
    assert data["ok"] is False
    assert "converter" in data["error"]


def test_voice_stt_no_pipeline(tmp_path, monkeypatch) -> None:
    sessions_file = tmp_path / "sessions.json"
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(sessions_file))
    monkeypatch.setattr("app.storage.session_store.DATA_DIR", str(tmp_path))
    PanelHandler.voice_pipeline = None

    import app.ui.panel.api.voice as voice_api_module
    monkeypatch.setattr(voice_api_module, "_fallback_pipeline", None)
    monkeypatch.setattr(
        "app.ui.panel.api.voice.VoicePipeline" if hasattr(voice_api_module, "VoicePipeline") else
        "app.services.voice.pipeline.VoicePipeline",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("Desabilitado no teste")),
        raising=False,
    )

    original_get_pipeline = voice_api_module._get_pipeline

    def _patched_get_pipeline(handler):
        pipeline = getattr(handler, "voice_pipeline", None)
        if pipeline is not None:
            return pipeline
        return None

    monkeypatch.setattr(voice_api_module, "_get_pipeline", _patched_get_pipeline)

    server = HTTPServer(("127.0.0.1", 0), PanelHandler)
    host, port = server.server_address
    PanelHandler.settings.port = port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://{host}:{port}"

    status, body = _request("POST", f"{base}/api/voice/stt", b"\x01", content_type="audio/webm")
    server.shutdown()
    thread.join(timeout=2)

    assert status == 503
    data = json.loads(body)
    assert data["ok"] is False
    assert "indispon" in data["error"]


def test_voice_tts_success(panel_http) -> None:
    base, pipeline = panel_http
    pipeline.synthesize_bytes.return_value = b"\xff\xfb" + b"\x00" * 32

    status, body = _request(
        "POST",
        f"{base}/api/voice/tts",
        json.dumps({"text": "Resposta do Jarvis"}).encode(),
    )
    assert status == 200
    assert body.startswith(b"\xff\xfb")
    pipeline.synthesize_bytes.assert_called_once_with("Resposta do Jarvis")


def test_voice_tts_empty_text(panel_http) -> None:
    base, pipeline = panel_http
    status, body = _request("POST", f"{base}/api/voice/tts", json.dumps({"text": "  "}).encode())
    assert status == 400
    data = json.loads(body)
    assert data["ok"] is False
    assert "vazio" in data["error"].lower()
    pipeline.synthesize_bytes.assert_not_called()


def test_voice_tts_failure(panel_http) -> None:
    base, pipeline = panel_http
    pipeline.synthesize_bytes.return_value = None

    status, body = _request(
        "POST",
        f"{base}/api/voice/tts",
        json.dumps({"text": "Falha"}).encode(),
    )
    assert status == 500
    data = json.loads(body)
    assert data["ok"] is False
    assert "sintetizar" in data["error"].lower()


def test_voice_tts_invalid_json(panel_http) -> None:
    base, _ = panel_http
    status, body = _request("POST", f"{base}/api/voice/tts", b"{invalid")
    assert status == 400
    data = json.loads(body)
    assert data["ok"] is False


def test_pipeline_transcribe_bytes_delegates_to_stt() -> None:
    settings = Settings()
    pipeline = VoicePipeline(settings)
    with patch.object(pipeline.stt, "transcribe_file", return_value=("texto", None)) as stt_mock:
        result = pipeline.transcribe_bytes(b"audio", suffix=".webm")
    assert result["text"] == "texto"
    assert result["ok"] is True
    assert result["error"] is None
    stt_mock.assert_called_once()
    path_arg = stt_mock.call_args[0][0]
    assert path_arg.endswith(".webm")


def test_pipeline_transcribe_empty_bytes() -> None:
    settings = Settings()
    pipeline = VoicePipeline(settings)
    result = pipeline.transcribe_bytes(b"")
    assert result["ok"] is False
    assert result["error"]


def test_prepare_audio_for_stt_raises_when_conversion_fails(tmp_path) -> None:
    webm = tmp_path / "clip.webm"
    webm.write_bytes(b"\x00" * 16)
    with patch("app.services.voice.audio_convert.convert_to_wav", return_value=None):
        with pytest.raises(AudioConversionError) as exc:
            prepare_audio_for_stt(str(webm))
    assert "converter" in exc.value.message.lower()


def test_llm_voice_intent_detection() -> None:
    settings = Settings()
    llm = LLMService(settings=settings)
    assert llm.detect_intent("quero usar voz") == "voice"


def test_chat_session_voice_fallback() -> None:
    orchestrator = MagicMock()
    orchestrator.handle_request.return_value = MagicMock(intent="voice", summary="", actions=[], context={})
    session = ChatSession(orchestrator)
    reply = session.handle_message("ativar voz")
    assert reply["intent"] == "voice"
    assert "voz" in reply["message"].lower()


def test_orchestrator_llm_fallback_when_no_api_key(isolated_conversation_journal) -> None:
    settings = Settings()
    settings.gemini_api_key = ""
    settings.groq_api_key = ""
    llm = LLMService(settings=settings)
    orchestrator = AgentOrchestrator(settings=settings, llm_service=llm)
    plan = orchestrator.handle_request("explique física")
    assert plan.intent == "error"
    assert "GEMINI_API_KEY" in plan.summary or "GROQ_API_KEY" in plan.summary
