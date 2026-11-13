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
    monkeypatch.setattr(vision.VisionService, '_validate_groq_model', lambda self: None)
    service = vision.VisionService(groq_api_key='fake', provider='groq')
    def create(**kwargs):
        assert kwargs['model'] == service.groq_model
        assert kwargs['messages'][0] == {'role': 'system', 'content': vision.VISION_SYSTEM_PROMPT}
        if failure:
            raise RuntimeError('model_not_found')
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Uma tela.'))])
    monkeypatch.setattr(service, '_get_client', lambda *args: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    result = service.analyze('Descreva', vision.Image.new('RGB', (1, 1)))
    assert result['ok'] is not failure
    assert ('model_not_found' in result['reply']) is failure


def test_tool_preserves_visual_failure(monkeypatch):
    from app.agent.tools.vision_tool import VisionTool
    monkeypatch.setattr(vision.VisionService, 'capture_pil', lambda self: vision.Image.new('RGB', (1, 1)))
    monkeypatch.setattr(vision.VisionService, 'analyze', lambda *args, **kwargs: {'ok': False, 'reply': 'API indisponível'})
    assert VisionTool().execute({'action': 'analyze_screen'}).ok is False


def test_vision_does_not_recapture_after_failure_or_unknown_action(monkeypatch):
    from app.agent.tools.vision_tool import VisionTool
    captures = []
    monkeypatch.setattr(vision.VisionService, 'capture_pil', lambda self: captures.append(True))
    monkeypatch.setattr(vision.VisionService, 'analyze', lambda *a, **kw: pytest.fail('No image to analyze'))
    assert not VisionTool().execute({'action': 'unknown'}).ok
    assert not captures
    assert not VisionTool().execute({'action': 'analyze_screen'}).ok
    assert len(captures) == 1


def test_visual_receipt_has_source_and_capture_time(monkeypatch):
    from app.agent.tools.vision_tool import VisionTool
    monkeypatch.setattr(vision.VisionService, 'capture_pil', lambda self: vision.Image.new('RGB', (1, 1)))
    monkeypatch.setattr(vision.VisionService, 'analyze', lambda *a, **kw: {'ok': True, 'reply': 'Uma janela.', 'provider': 'groq', 'model': 'test-vision'})
    result = VisionTool().execute({'action': 'analyze_screen'})
    assert result.ok and result.data['source'] == 'screen'
    assert result.data['captured_at'] in result.message
    assert 'provedor: groq; modelo: test-vision' in result.message


@pytest.mark.parametrize('provider', ['groq', 'gemini'])
@pytest.mark.parametrize('use_bytes', [False, True])
def test_grounding_reaches_both_providers_and_entrypoints(monkeypatch, tmp_path, provider, use_bytes):
    monkeypatch.setattr(vision, 'CAPTURES_DIR', tmp_path)
    monkeypatch.setattr(vision.VisionService, '_validate_groq_model', lambda self: None)
    service = vision.VisionService(api_key='gemini-test', groq_api_key='groq-test', provider=provider)
    def generate(**kw):
        assert kw['config'].system_instruction == vision.VISION_SYSTEM_PROMPT
        return SimpleNamespace(text='Imagem recebida.')
    def create(**kw):
        assert kw['messages'][0]['content'] == vision.VISION_SYSTEM_PROMPT
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='Imagem recebida.'))])
    client = SimpleNamespace(models=SimpleNamespace(generate_content=generate),
                             chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(service, '_get_client', lambda *a: client)
    if use_bytes:
        result = service.analyze_bytes('Descreva', b'image')
    else:
        result = service.analyze('Descreva', vision.Image.new('RGB', (1, 1)))['reply']
    assert result == 'Imagem recebida.'


def test_groq_validation_initializes_and_caches_without_secret_collision(monkeypatch):
    calls = []
    monkeypatch.setattr(vision, '_GROQ_MODEL_VALIDATION_CACHE', {})
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: calls.append(kw))))
    monkeypatch.setattr(vision.VisionService, '_get_client', lambda *args: client)
    vision.VisionService(provider='groq', groq_api_key='first-test-key-same')
    vision.VisionService(provider='groq', groq_api_key='first-test-key-same')
    vision.VisionService(provider='groq', groq_api_key='second-test-key-same')
    assert len(calls) == 2
    assert not any('test-key' in key for key in vision._GROQ_MODEL_VALIDATION_CACHE)


def test_visual_provider_can_be_selected_without_changing_chat(monkeypatch):
    monkeypatch.setattr(vision.VisionService, '_validate_groq_model', lambda self: None)
    settings = SimpleNamespace(llm_provider='groq', vision_provider='gemini',
                               gemini_api_key='gemini-test', groq_api_key='groq-test',
                               gemini_vision_model='visual-model')
    service = vision.VisionService.from_settings(settings)
    assert service.provider == 'gemini' and service.model == 'visual-model'
    assert service.api_key == 'gemini-test' and service.groq_api_key == 'groq-test'
    assert settings.llm_provider == 'groq'
    settings.vision_provider = ''
    assert vision.VisionService.from_settings(settings).provider == 'groq'
    settings.vision_provider = 'unsupported'
    with pytest.raises(ValueError, match='VISION_PROVIDER'):
        vision.VisionService.from_settings(settings)


@pytest.mark.parametrize('known_invalid', [False, True])
@pytest.mark.parametrize('use_bytes', [False, True])
def test_visual_fallback_uses_gemini_credentials(monkeypatch, tmp_path, known_invalid, use_bytes):
    monkeypatch.setattr(vision, 'CAPTURES_DIR', tmp_path)
    monkeypatch.setattr(vision.VisionService, '_validate_groq_model', lambda self: None)
    service = vision.VisionService.from_settings(SimpleNamespace(
        llm_provider='groq', gemini_api_key='gemini-test', groq_api_key='groq-test'))
    service._groq_model_invalid = known_invalid
    calls = []
    def get_client(provider, key):
        calls.append((provider, key))
        if provider == 'groq':
            def create(**kwargs):
                raise RuntimeError('model_not_found')
            return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        assert key == 'gemini-test'
        return SimpleNamespace(models=SimpleNamespace(
            generate_content=lambda **kwargs: SimpleNamespace(text='Observação Gemini.')))
    monkeypatch.setattr(service, '_get_client', get_client)
    if use_bytes:
        assert service.analyze_bytes('Descreva', b'image') == 'Observação Gemini.'
    else:
        result = service.analyze('Descreva', vision.Image.new('RGB', (1, 1)))
        assert result['ok'] and result['reply'] == 'Observação Gemini.'
        assert result['provider'] == 'gemini' and result['model'] == service.model
    assert calls == ([] if known_invalid else [('groq', 'groq-test')]) + [('gemini', 'gemini-test')]


def test_missing_groq_key_never_uses_gemini_key(monkeypatch, tmp_path):
    monkeypatch.setattr(vision, 'CAPTURES_DIR', tmp_path)
    service = vision.VisionService(api_key='gemini-only', provider='groq')
    monkeypatch.setattr(service, '_get_client', lambda *a: pytest.fail('Do not send a key to another provider'))
    result = service.analyze('Descreva', vision.Image.new('RGB', (1, 1)))
    assert not result['ok'] and 'Chave de API do Groq' in result['reply']
