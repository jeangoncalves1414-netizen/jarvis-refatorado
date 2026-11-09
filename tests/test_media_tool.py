"""Testes para a ferramenta de mídia, vídeos motivacionais e streaming seguro."""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agent.tools.media_tool import (
    MediaTool,
    get_project_root,
    get_motivational_videos_dir,
    validate_safe_path,
)
from app.agent.tools.image_generator import ImageGeneratorTool
from app.agent.tools.registry import ToolRegistry
from app.agent.tools.catalog import metadata_for
from app.ui.panel.api.media import (
    validate_media_stream_path,
    validate_reveal_path,
    handle_media_stream,
    handle_media_reveal,
)


@pytest.fixture
def temp_media_environment(tmp_path: Path):
    """Cria um ambiente temporário com vídeos de teste."""
    motivational_dir = tmp_path / "data" / "videos" / "motivacionais"
    motivational_dir.mkdir(parents=True, exist_ok=True)

    # Cria arquivos de teste
    video1 = motivational_dir / "foco_e_disciplina.mp4"
    video1.write_bytes(b"FAKE_MP4_CONTENT_1234567890" * 10)

    video2 = motivational_dir / "superacao_diaria.webm"
    video2.write_bytes(b"FAKE_WEBM_CONTENT_0987654321" * 8)

    video3 = motivational_dir / "motivacao_matinal.mkv"
    video3.write_bytes(b"FAKE_MKV_CONTENT_1122334455" * 6)

    # Arquivo não suportado (não deve ser listado como vídeo)
    ignored = motivational_dir / "notas.txt"
    ignored.write_text("texto qualquer")

    return {
        "root": tmp_path,
        "motivational_dir": motivational_dir,
        "video1": video1,
        "video2": video2,
        "video3": video3,
        "ignored": ignored,
    }


# ─── 1. Testes de listagem de vídeos ──────────────────────────────────────────

def test_list_videos_default_folder(temp_media_environment):
    env = temp_media_environment
    tool = MediaTool(base_folder=env["motivational_dir"])

    res = tool.execute({"action": "list_videos"})
    assert res.ok is True
    assert "Encontrado(s) 3 vídeo(s)" in res.message
    assert res.data["count"] == 3

    names = [v["name"] for v in res.data["videos"]]
    assert "foco_e_disciplina.mp4" in names
    assert "superacao_diaria.webm" in names
    assert "motivacao_matinal.mkv" in names
    assert "notas.txt" not in names


def test_list_videos_query_filter(temp_media_environment):
    env = temp_media_environment
    tool = MediaTool(base_folder=env["motivational_dir"])

    res = tool.execute({"action": "list_videos", "query": "foco"})
    assert res.ok is True
    assert res.data["count"] == 1
    assert res.data["videos"][0]["name"] == "foco_e_disciplina.mp4"

    res_empty = tool.execute({"action": "list_videos", "query": "inexistente"})
    assert res_empty.ok is True
    assert res_empty.data["count"] == 0
    assert "Nenhum vídeo encontrado" in res_empty.message


# ─── 2. Testes de reprodução motivacional e payload __MEDIA_VIEW__ ────────────

def test_play_motivational_payload_and_marker(temp_media_environment):
    env = temp_media_environment
    tool = MediaTool(base_folder=env["motivational_dir"])

    res = tool.execute({"action": "play_motivational", "query": "foco"})
    assert res.ok is True
    assert "__MEDIA_VIEW__" in res.message

    # Valida formato do JSON emitido no marcador
    marker_idx = res.message.index("__MEDIA_VIEW__")
    json_str = res.message[marker_idx + len("__MEDIA_VIEW__"):].strip()
    payload = json.loads(json_str)

    assert payload["type"] == "video"
    assert "/api/media/stream?file=" in payload["url"]
    assert "foco_e_disciplina.mp4" in payload["url"]
    assert Path(payload["path"]).name == "foco_e_disciplina.mp4"
    assert "Foco E Disciplina" in payload["title"]


def test_play_motivational_empty_directory(tmp_path: Path):
    empty_dir = tmp_path / "empty_videos"
    empty_dir.mkdir(parents=True, exist_ok=True)
    tool = MediaTool(base_folder=empty_dir)

    res = tool.execute({"action": "play_motivational"})
    assert res.ok is False
    assert "Nenhum vídeo motivacional encontrado" in res.message


# ─── 3. Teste de payload __MEDIA_VIEW__ em ImageGeneratorTool ─────────────────

def test_image_generator_emits_media_view_marker():
    tool = ImageGeneratorTool()

    fake_result = MagicMock()
    fake_item = MagicMock()
    fake_item.url = "https://images.fake-service.local/sample.png"
    fake_result.data = [fake_item]

    fake_client = MagicMock()
    fake_client.images.generate.return_value = fake_result

    with patch("openai.OpenAI", return_value=fake_client):
        settings_mock = MagicMock()
        settings_mock.oxyy_api_keys = ["sk-fake-key"]
        settings_mock.oxyy_base_url = "https://fake.url"
        settings_mock.oxyy_image_model = "dall-e-3"
        ctx = {"settings": settings_mock}
        res = tool.execute({"prompt": "um robô futurista em neon azul"}, context=ctx)

        assert res.ok is True
        assert "__MEDIA_VIEW__" in res.message
        marker_idx = res.message.index("__MEDIA_VIEW__")
        payload = json.loads(res.message[marker_idx + len("__MEDIA_VIEW__"):].strip())

        assert payload["type"] == "image"
        assert payload["url"] == "https://images.fake-service.local/sample.png"
        assert "robô futurista" in payload["title"]


# ─── 4. Segurança contra Directory Traversal ──────────────────────────────────

def test_validate_safe_path_directory_traversal():
    # Caminhos que tentam subir níveis além da raiz
    with pytest.raises(PermissionError):
        validate_safe_path("../../../../../Windows/System32/calc.exe")

    if sys.platform == "win32":
        with pytest.raises(PermissionError):
            validate_safe_path("C:\\Windows\\System32\\cmd.exe")
    else:
        with pytest.raises(PermissionError):
            validate_safe_path("/etc/passwd")

    with pytest.raises(ValueError):
        validate_safe_path("data/videos/\0malicious.mp4")


def test_validate_media_stream_path_traversal():
    with pytest.raises(PermissionError) as exc_info:
        validate_media_stream_path("../../app/ui/panel/server.py")
    assert "directory traversal" in str(exc_info.value).lower()

    with pytest.raises(PermissionError):
        validate_media_stream_path("../../../etc/passwd")

    # Arquivo fora da pasta permitida mesmo com extensão mp4
    with pytest.raises(PermissionError):
        validate_media_stream_path("../../secret_video.mp4")


def test_reveal_in_folder_security_and_execution():
    tool = MediaTool()

    # Tentativa de traversal
    res = tool.execute({"action": "reveal_in_folder", "path": "../../../../../Windows/System32/cmd.exe"})
    assert res.ok is False
    assert "Erro de segurança" in res.message

    # Arquivo inexistente
    res_not_found = tool.execute({"action": "reveal_in_folder", "path": "data/videos/arquivo_fantasma.mp4"})
    assert res_not_found.ok is False
    assert "não encontrado" in res_not_found.message.lower()

    # Arquivo real existente
    root = get_project_root()
    test_file = root / "data" / "videos" / "motivacionais" / ".gitkeep"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.touch(exist_ok=True)

    with patch("subprocess.Popen") as mock_popen:
        res_ok = tool.execute({"action": "reveal_in_folder", "path": str(test_file)})
        assert res_ok.ok is True
        assert "Arquivo selecionado no Windows Explorer" in res_ok.message
        if sys.platform == "win32":
            assert mock_popen.called


# ─── 5. Testes da API HTTP de revelação e streaming ───────────────────────────

def test_api_media_reveal_validation():
    # Requisição com caminho de traversal
    status, data = handle_media_reveal(
        "/api/media/reveal",
        json.dumps({"path": "../../../../../Windows/System32/notepad.exe"}).encode("utf-8"),
        MagicMock(),
    )
    assert status == 403
    assert data["ok"] is False

    # Requisição com arquivo inexistente
    status, data = handle_media_reveal(
        "/api/media/reveal",
        json.dumps({"path": "data/videos/motivacionais/nao_existe.mp4"}).encode("utf-8"),
        MagicMock(),
    )
    assert status == 404
    assert data["ok"] is False

    # Requisição com payload inválido
    status, data = handle_media_reveal("/api/media/reveal", b"invalid-json", MagicMock())
    assert status == 400
    assert data["ok"] is False

    # Requisição válida com arquivo real
    root = get_project_root()
    test_file = root / "data" / "videos" / "motivacionais" / ".gitkeep"
    with patch("subprocess.Popen"):
        status, data = handle_media_reveal(
            "/api/media/reveal",
            json.dumps({"path": str(test_file)}).encode("utf-8"),
            MagicMock(),
        )
        assert status == 200
        assert data["ok"] is True


def test_api_media_stream_headers_and_ranges(temp_media_environment):
    env = temp_media_environment
    video_file = env["video1"]
    content = video_file.read_bytes()
    total_size = len(content)

    # Patch get_project_root para apontar para o temp root
    with patch("app.ui.panel.api.media.get_project_root", return_value=env["root"]):
        # 1. Requisição completa (sem header Range)
        handler_full = MagicMock()
        handler_full.path = "/api/media/stream?file=motivacionais/foco_e_disciplina.mp4"
        handler_full.headers = {}
        written_buffer = BytesIO()
        handler_full.wfile.write.side_effect = written_buffer.write

        handle_media_stream(handler_full)

        handler_full.send_response.assert_called_with(200)
        handler_full.send_header.assert_any_call("Accept-Ranges", "bytes")
        handler_full.send_header.assert_any_call("Content-Length", str(total_size))
        assert written_buffer.getvalue() == content

        # 2. Requisição com header Range parcial (bytes=0-49)
        handler_range = MagicMock()
        handler_range.path = "/api/media/stream?file=motivacionais/foco_e_disciplina.mp4"
        handler_range.headers = {"Range": "bytes=0-49"}
        range_buffer = BytesIO()
        handler_range.wfile.write.side_effect = range_buffer.write

        handle_media_stream(handler_range)

        handler_range.send_response.assert_called_with(206)
        handler_range.send_header.assert_any_call("Content-Range", f"bytes 0-49/{total_size}")
        handler_range.send_header.assert_any_call("Content-Length", "50")
        assert range_buffer.getvalue() == content[:50]

        # 3. Requisição com Range fora do limite (bytes=9999-)
        handler_invalid_range = MagicMock()
        handler_invalid_range.path = "/api/media/stream?file=motivacionais/foco_e_disciplina.mp4"
        handler_invalid_range.headers = {"Range": "bytes=9999-"}

        handle_media_stream(handler_invalid_range)
        handler_invalid_range.send_response.assert_called_with(416)


# ─── 6. Testes de registro no ToolRegistry e Catálogo ─────────────────────────

def test_media_tool_in_registry_and_catalog():
    registry = ToolRegistry()
    assert "media_tool" in registry.tools
    tool = registry.tools["media_tool"]
    assert isinstance(tool, MediaTool)

    meta = metadata_for("media_tool", tool)
    assert meta is not None
    assert "media" in meta.capabilities
    operations = [op for op, _ in meta.operation_risks]
    assert "list_videos" in operations
    assert "play_motivational" in operations
    assert "reveal_in_folder" in operations
