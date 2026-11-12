from types import SimpleNamespace
import pytest

from app.services import vision


def test_capture_uses_mss_factory(monkeypatch):
    class Capture:
        monitors = ["desktop"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def grab(self, monitor):
            assert monitor == "desktop"
            return SimpleNamespace(size=(1, 1), rgb=b"\xff\x00\x00")

    monkeypatch.setattr(vision, "mss", lambda: Capture())
    service = vision.VisionService()
    assert service.capture_pil().getpixel((0, 0)) == (255, 0, 0)
    assert service.capture_screen() == b"\xff\x00\x00"


@pytest.mark.parametrize("failure", [False, True])
def test_visual_api_failure_is_not_success(monkeypatch, tmp_path, failure):
    monkeypatch.setattr(vision, 'CAPTURES_DIR', tmp_path)
    service = vision.VisionService(api_key='fake', provider='groq')
    def create(**kwargs):
        assert kwargs['model'] == service.groq_model
        if failure:
            raise RuntimeError('model_not_found')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Uma tela.'))])
    monkeypatch.setattr(service, '_get_client', lambda *args: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = service.analyze('Descreva', vision.Image.new('RGB', (1, 1)))
    assert result['ok'] is not failure
    assert ('model_not_found' in result['reply']) is failure


def test_tool_preserves_visual_failure(monkeypatch):
    from app.agent.tools.vision_tool import VisionTool
    monkeypatch.setattr(vision.VisionService, 'capture_pil', lambda self: None)
    monkeypatch.setattr(vision.VisionService, 'analyze', lambda *args, **kwargs: {'ok': False, 'reply': 'API indisponível'})
    assert VisionTool().execute({'action': 'analyze_screen'}).ok is False
