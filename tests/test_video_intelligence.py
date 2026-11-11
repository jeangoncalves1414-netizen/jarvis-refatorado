"""Testes unitários e de integração para VideoIntelligenceService e VideoAnalystTool."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch
import pytest

from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.registry import ToolRegistry, GENERAL_TOOL_NAMES
from app.agent.tools.video_analyst_tool import VideoAnalystTool
from app.services.video_intelligence import (
    VideoIntelligenceService,
    extract_youtube_id,
    format_timestamp,
    get_video_intelligence_service,
)


def test_extract_youtube_id():
    assert extract_youtube_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_id("https://www.youtube.com/shorts/dQw4w9WgXcQ?feature=share") == "dQw4w9WgXcQ"
    assert extract_youtube_id("https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_id("https://www.youtube.com/watch?other=param&v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert extract_youtube_id("texto_invalido_sem_video") is None
    assert extract_youtube_id("") is None


def test_format_timestamp():
    assert format_timestamp(0) == "[00:00]"
    assert format_timestamp(45) == "[00:45]"
    assert format_timestamp(65) == "[01:05]"
    assert format_timestamp(3600) == "[01:00:00]"
    assert format_timestamp(3665) == "[01:01:05]"


def test_video_analyst_tool_catalog_metadata():
    assert "video_analyst" in TOOL_CATALOG
    metadata = TOOL_CATALOG["video_analyst"]
    assert "video" in metadata.capabilities
    assert metadata.default_risk == "observe"
    assert metadata.risk_for({"action": "analyze_youtube_video"}) == "observe"
    assert metadata.risk_for({"action": "analyze_local_video"}) == "observe"
    assert metadata.risk_for({"action": "find_moments"}) == "observe"


def test_video_analyst_tool_registry(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    assert "video_analyst" in registry.tools
    assert "video_analyst" in GENERAL_TOOL_NAMES
    tool = registry.tools["video_analyst"]
    assert isinstance(tool, VideoAnalystTool)
    assert tool.name == "video_analyst"
    assert "action" in tool.parameters["properties"]


def test_analyze_local_video_file_not_found():
    service = VideoIntelligenceService()
    with pytest.raises(FileNotFoundError):
        service.analyze_local_video("/caminho/inexistente/video.mp4")


def test_analyze_local_video_no_api_key(tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"dummy video data")

    service = VideoIntelligenceService()
    with patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=True):
        fake_settings = MagicMock(gemini_api_key="", gemini_api_keys=[])
        with pytest.raises(ValueError, match="GEMINI_API_KEY"):
            service.analyze_local_video(str(video_file), settings=fake_settings)


def test_analyze_local_video_success_with_cleanup(tmp_path):
    video_file = tmp_path / "sample.mp4"
    video_file.write_bytes(b"dummy video data")

    fake_uploaded_file = MagicMock()
    fake_uploaded_file.name = "files/test-video-uuid"
    fake_uploaded_file.state.name = "ACTIVE"

    fake_response = MagicMock()
    fake_response.text = "O vídeo demonstra a interface do Jarvis com comandos de voz."

    mock_client = MagicMock()
    mock_client.files.upload.return_value = fake_uploaded_file
    mock_client.models.generate_content.return_value = fake_response

    service = VideoIntelligenceService()
    fake_settings = MagicMock(gemini_api_key="fake-key-123")

    with patch("google.genai.Client", return_value=mock_client):
        res = service.analyze_local_video(
            str(video_file),
            prompt="Descreva o vídeo",
            settings=fake_settings,
        )

        assert "interface do Jarvis" in res
        mock_client.files.upload.assert_called_once_with(file=str(video_file))
        mock_client.models.generate_content.assert_called_once()
        # Garante que o arquivo remoto foi deletado após a análise
        mock_client.files.delete.assert_called_once_with(name="files/test-video-uuid")


def test_analyze_youtube_video_success():
    service = VideoIntelligenceService()
    mock_snippets = [
        {"text": "Bem-vindos ao tutorial de inteligência artificial.", "start": 0.0, "duration": 5.0},
        {"text": "Aqui explicamos a navegação autônoma.", "start": 125.0, "duration": 8.0},
    ]

    fake_llm_response = (
        "No início do vídeo [00:00], o apresentador dá as boas-vindas. "
        "Aos [02:05], é abordado o tema de navegação autônoma."
    )

    with patch.object(service, "_fetch_transcript_snippets", return_value=mock_snippets), \
         patch("app.services.llm.LLMService.ask", return_value=fake_llm_response):

        res = service.analyze_youtube_video(
            url_or_id="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            question="Qual o tema aos 2 minutos?",
        )

        assert res["ok"] is True
        assert res["video_id"] == "dQw4w9WgXcQ"
        assert "[02:05]" in res["analysis"]
        assert res["total_snippets"] == 2
        assert "[00:00] Bem-vindos" in res["transcript_preview"]


def test_find_moments_youtube():
    service = VideoIntelligenceService()
    mock_snippets = [
        {"text": "Apresentação inicial.", "start": 10.0},
        {"text": "Falando sobre o modelo Gemini Flash.", "start": 80.0},
    ]

    with patch.object(service, "_fetch_transcript_snippets", return_value=mock_snippets), \
         patch("app.services.llm.LLMService.ask", return_value="O modelo Gemini Flash é mencionado em [01:20]."):

        res = service.find_moments(video_source="dQw4w9WgXcQ", query="Gemini Flash")
        assert res["ok"] is True
        assert "[01:20]" in res["analysis"]


def test_video_analyst_tool_execution():
    tool = VideoAnalystTool()

    mock_service = MagicMock()
    mock_service.analyze_youtube_video.return_value = {
        "ok": True,
        "video_id": "dQw4w9WgXcQ",
        "analysis": "Análise completa do vídeo do YouTube.",
    }
    mock_service.analyze_local_video.return_value = "Análise do vídeo local concluída."
    mock_service.find_moments.return_value = {
        "ok": True,
        "analysis": "Momento encontrado em [03:15].",
    }

    tool._service = mock_service

    # Teste analyze_youtube_video
    res_yt = tool.execute({"action": "analyze_youtube_video", "url": "https://youtu.be/dQw4w9WgXcQ"})
    assert res_yt.ok is True
    assert "YouTube" in res_yt.message

    # Teste analyze_local_video
    res_local = tool.execute({"action": "analyze_local_video", "file_path": "video.mp4", "prompt": "analisar"})
    assert res_local.ok is True
    assert "local" in res_local.message

    # Teste find_moments
    res_moments = tool.execute({"action": "find_moments", "url": "dQw4w9WgXcQ", "query": "conceito"})
    assert res_moments.ok is True
    assert "[03:15]" in res_moments.message

    # Teste ação desconhecida
    res_err = tool.execute({"action": "unknown_action"})
    assert res_err.ok is False


def test_video_exclusive_routing_youtube_url(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    prompt = "Analise o video do youtube https://www.youtube.com/watch?v=dQw4w9WgXcQ e me diga os principais tópicos em timestamps"
    
    # Testa para Groq (onde ocorria o sequestro pelo web_search)
    allowed_groq = registry.allowed_tool_names(mode="general", provider="groq", user_text=prompt)
    assert "video_analyst" in allowed_groq
    assert "web_search" not in allowed_groq
    assert "browser" not in allowed_groq
    assert "media_tool" not in allowed_groq

    # Testa para qualquer provedor geral
    allowed_gen = registry.allowed_tool_names(mode="general", provider="gemini", user_text=prompt)
    assert "video_analyst" in allowed_gen
    assert "web_search" not in allowed_gen


def test_video_exclusive_routing_keywords(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    prompts = [
        "resumo do video https://youtu.be/dQw4w9WgXcQ",
        "transcricao e topicos do video",
        "analise o video e extraia os momentos do video com timestamps",
    ]
    for p in prompts:
        allowed = registry.allowed_tool_names(mode="general", provider="groq", user_text=p)
        assert "video_analyst" in allowed, f"Falha para prompt: {p}"
        assert "web_search" not in allowed, f"web_search não foi excluído para prompt: {p}"


def test_web_search_does_not_hijack_youtube_url():
    from app.agent.tools.web_search import WebSearchTool

    tool = WebSearchTool()
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

    with patch("webbrowser.open") as mock_browser_open, \
         patch("app.agent.tools.video_analyst_tool.VideoAnalystTool.execute") as mock_video_exec:
        
        mock_video_exec.return_value = ToolResult(ok=True, message="Vídeo analisado via VideoAnalyst.")
        
        # Teste com action="open_url"
        res_open = tool.execute({"action": "open_url", "query": yt_url})
        assert res_open.ok is True
        assert "navegador" in res_open.message
        mock_browser_open.assert_called_once_with(yt_url)
        mock_video_exec.assert_not_called()

        mock_browser_open.reset_mock()
        mock_video_exec.reset_mock()
        # Teste com action="search"
        res_search = tool.execute({"action": "search", "query": "https://youtu.be/dQw4w9WgXcQ"})
        assert res_search.ok is True
        mock_browser_open.assert_not_called()
        mock_video_exec.assert_called_once()


def test_run_by_marker_reroutes_youtube_search_to_video_analyst(tmp_path):
    registry = ToolRegistry(base_folder=str(tmp_path))
    yt_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    user_line = f"Analise o video {yt_url}"

    with patch.object(registry.tools["video_analyst"], "execute", return_value=ToolResult(ok=True, message="Sucesso VideoAnalyst")) as mock_exec:
        res = registry.run_by_marker("web_search", yt_url, user_line)
        assert res.ok is True
        assert "Sucesso VideoAnalyst" in res.message
        mock_exec.assert_called_once()


