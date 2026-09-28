"""
Unit tests for QRReaderService, QRReaderTool, and REST endpoint /api/qr/read.
"""
from unittest.mock import patch, MagicMock
from app.services.qr_reader import QRReaderService, QRResult, QR_AVAILABLE
from app.agent.tools.qr_reader_tool import QRReaderTool
from app.agent.tools.registry import ToolRegistry


def test_qr_service_availability():
    avail = QRReaderService.availability()
    assert isinstance(avail, dict)
    assert "pyzbar" in avail
    assert "opencv" in avail
    assert "pil" in avail
    assert "mss" in avail
    assert "ready" in avail


def test_qr_service_base64_invalid():
    svc = QRReaderService()
    res = svc.read_from_base64("invalid_b64_data")
    assert isinstance(res, QRResult)
    # Should not crash, ok may be False or empty codes
    assert not res.ok or len(res.codes) == 0


def test_qr_tool_registration():
    reg = ToolRegistry()
    tool = reg.get_tool("qr_reader")
    assert tool is not None
    assert tool.name == "qr_reader"
    assert "source" in tool.parameters["properties"]


def test_qr_tool_execution_screen_mock():
    tool = QRReaderTool()
    with patch.object(QRReaderService, "read_from_screen") as mock_screen:
        mock_screen.return_value = QRResult(
            ok=True,
            codes=[{"data": "https://jarvis.ai", "type": "QRCODE", "rect": {"left": 10, "top": 10, "width": 50, "height": 50}}],
            source="screen",
            capture_time_ms=45.0,
        )
        res = tool.execute({"source": "screen"})
        assert res.ok
        assert "https://jarvis.ai" in res.message
        assert res.data["count"] == 1


def test_qr_tool_execution_camera_mock():
    tool = QRReaderTool()
    with patch.object(QRReaderService, "read_from_camera") as mock_cam:
        mock_cam.return_value = QRResult(
            ok=True,
            codes=[],
            source="camera",
            capture_time_ms=120.0,
        )
        res = tool.execute({"source": "camera"})
        assert res.ok
        assert "Nenhum QR Code" in res.message
