import base64
from io import BytesIO
import json

import pytest
from PIL import Image

from app.services import identity_observation as observation


@pytest.fixture
def faces(monkeypatch):
    profiles = [{'id': 'ana', 'name': 'Ana', 'face_embeddings_sface': [[1., 0.]]}]
    monkeypatch.setattr(observation, '_read', lambda: {'profiles': profiles})
    monkeypatch.setattr(observation.engine, 'extract', lambda raw: [{'embedding': [1., 0.]}])
    return profiles


@pytest.mark.parametrize('prompt', [
    'identifica quem aparece na câmera', 'Jarvis, identifique quem está na câmera',
    'Você consegue me reconhecer pela webcam?', 'Reconheça meu rosto pela câmera',
    'Quem aparece na câmera?',
])
def test_requested_identity_uses_local_profiles(faces, prompt):
    result = observation.camera_identity_answer(prompt, b'frame')
    assert result['ok'] and 'Ana' in result['reply']
    assert result['provider'] == 'local'


@pytest.mark.parametrize('state', ['unknown', 'ambiguous', 'probable', 'unenrolled', 'no_face'])
def test_does_not_guess_identity(faces, monkeypatch, state):
    if state == 'unknown':
        faces[0]['face_embeddings_sface'] = [[-1., 0.]]
    elif state == 'ambiguous':
        faces.append({'id': 'bia', 'name': 'Bia', 'face_embeddings_sface': [[1., 0.]]})
    elif state == 'probable':
        faces[0]['face_embeddings_sface'] = [[0.52, 0.85416626]]
    elif state == 'unenrolled':
        faces[0].pop('face_embeddings_sface')
    else:
        monkeypatch.setattr(observation.engine, 'extract', lambda raw: [])
    result = observation.camera_identity_answer('identifica quem aparece na câmera', b'frame')
    assert result['ok'] and 'Ana' not in result['reply'] and 'Bia' not in result['reply']
    if state == 'unenrolled':
        assert 'cadastro do rosto' in result['reply']
    if state == 'no_face':
        assert 'Não detectei' in result['reply']


def test_missing_model_returns_actionable_error(monkeypatch):
    def missing(raw):
        raise ValueError('Prepare o modelo facial local na página Identidade.')
    monkeypatch.setattr(observation.engine, 'extract', missing)
    result = observation.camera_identity_answer('Quem aparece na câmera?', b'frame')
    assert not result['ok'] and 'Identidade' in result['error']


@pytest.mark.parametrize('prompt', ['Descreva a câmera', 'Qual objeto está na câmera?', 'Quem fabricou este objeto?'])
def test_other_visual_requests_do_not_run_face_recognition(monkeypatch, prompt):
    monkeypatch.setattr(observation.engine, 'extract', lambda _: pytest.fail('Unexpected face inference'))
    assert observation.camera_identity_answer(prompt, b'frame') is None


def test_frame_endpoint_identifies_without_cloud_vision(faces, monkeypatch):
    from app.ui.panel.server import PanelHandler
    from app.services.vision import VisionService
    monkeypatch.setattr(VisionService, 'from_settings', lambda _: pytest.fail('Identity must stay local'))
    image = BytesIO()
    Image.new('RGB', (8, 8)).save(image, format='JPEG')
    raw = image.getvalue()
    def extract(received):
        assert received == raw
        return [{'embedding': [1., 0.]}]
    monkeypatch.setattr(observation.engine, 'extract', extract)
    body = json.dumps({'prompt': 'identifica quem aparece na câmera',
                       'image': 'data:image/jpeg;base64,' + base64.b64encode(raw).decode()}).encode()
    handler = object.__new__(PanelHandler)
    handler.path = '/api/vision/analyze-frame'
    handler.command = 'POST'
    handler.headers = {'Content-Length': str(len(body))}
    handler.rfile = BytesIO(body)
    handler._authorize_api = lambda *args, **kwargs: {'kind': 'local'}
    sent = []
    handler._send_json = lambda status, data: sent.append((status, data))
    handler.do_POST()
    assert sent[0][0] == 200
    assert 'Ana' in sent[0][1]['reply']


def test_camera_wording_uses_measured_identity_without_private_history(faces):
    from types import SimpleNamespace
    calls = []
    def build(history, text):
        assert history == []
        assert json.loads(text)['rostos'] == ['Ana']
        assert 'embedding' not in text
        return text
    def generate(contents, **kwargs):
        calls.append(kwargs)
        return SimpleNamespace(text='Estou vendo a Ana por aqui.')
    result = observation.camera_identity_answer('Quem você vê?', b'frame', llm=SimpleNamespace(build_contents=build, generate=generate))
    assert result['reply'] == 'Estou vendo a Ana por aqui.'
    assert calls[0]['tools'] is None


def test_camera_provider_failure_preserves_local_observation(faces):
    from types import SimpleNamespace
    def fail(*args):
        raise RuntimeError('offline')
    result = observation.camera_identity_answer('Quem você vê?', b'frame', llm=SimpleNamespace(build_contents=fail))
    assert result['ok'] and 'Ana' in result['reply']
