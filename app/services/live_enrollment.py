"""Validate a guided introduction before persisting the new profile."""
import secrets
import time
import threading
import json
import math
import re
import unicodedata
from collections import Counter

from app.services import identity
from app.services.face_identity import engine as faces

_pending = {}
_lock = threading.RLock()
READING = 'Eu autorizo o Jarvis a reconhecer minha voz durante nossas conversas. Hoje estou lendo este texto com calma para criar minha referência pessoal.'
VOICE_READINGS = (READING, 'Jarvis, quem está falando agora com você neste computador?',
                  'Pode me dizer como está o tempo hoje na minha cidade?')
MIN_READING_COVERAGE = 0.80


def reading_coverage(phrase, heard):
    def words(text):
        normalized = ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))
        return re.findall(r'[a-z0-9]+', normalized)
    expected = Counter(words(phrase))
    matched = sum((expected & Counter(words(heard))).values())
    return matched / sum(expected.values()) if expected else 0.0


def authorize(payload):
    replacing = payload.get('purpose') == 'admin_reenroll'
    if replacing:
        return authorize_admin_reenrollment(payload)
    name = str(payload.get('name') or '').strip()
    if not 2 <= len(name) <= 80:
        raise ValueError('Informe o nome da pessoa.')
    profiles = identity._read().get('profiles', [])
    if any(p.get('name', '').casefold() == name.casefold() for p in profiles):
        raise ValueError('Já existe um perfil com este nome.')
    return _issue_ticket(name, None)


def authorize_admin_reenrollment(payload):
    """Replacing administrator biometrics always requires the current password."""
    with _lock, identity._profile_lock:
        from app.services.app_lock import app_lock
        authorization = app_lock.authorize_identity(payload.get('admin_password'))
        profiles = identity._read().get('profiles', [])
        admin = next((p for p in profiles if p.get('role') == 'admin'), None)
        name = admin['name'] if admin else str(payload.get('name') or '').strip()
        if not 2 <= len(name) <= 80:
            raise ValueError('Informe seu nome para criar o primeiro administrador.')
        result = _issue_ticket(name, admin, purpose='admin_reenroll' if admin else 'admin_create')
        _pending[result['ticket']]['unlock_password'] = authorization
        return result


def _issue_ticket(name, admin, purpose='user'):
    token = secrets.token_urlsafe(24)
    with _lock:
        for key in list(_pending):
            if _pending[key]['expires'] < time.monotonic():
                del _pending[key]
        if len(_pending) >= 32:
            raise ValueError('Há muitos cadastros pendentes. Aguarde e tente novamente.')
        _pending[token] = {'name': name, 'expires': time.monotonic() + 600, 'admin_id': admin['id'] if admin else None,
                           'admin_revision': admin.get('identity_revision', 0) if admin else None, 'purpose': purpose}
    return {'ok': True, 'ticket': token, 'phrase': READING, 'name': name}


def _session(ticket):
    state = _pending.get(ticket) if isinstance(ticket, str) else None
    if not state or state['expires'] < time.monotonic():
        raise ValueError('O cadastro expirou. Apresente a pessoa novamente.')
    return state


def transcribe_reading(raw, content_type):
    import numpy as np
    samples = identity.voice_identity_engine._decode_audio(raw, content_type)
    if len(samples) > 45 * 16000:
        raise ValueError('A leitura deve durar até 45 segundos.')
    return transcribe_pcm((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())


def transcribe_pcm(pcm):
    """Keep finalized phrases as well as the last partial phrase after a pause."""
    import vosk
    from app.services.voice.wake_word import _get_model
    model = _get_model(download=True)
    if model is None:
        raise ValueError('O leitor local de português está indisponível. Prepare o reconhecimento de fala.')
    reader = vosk.KaldiRecognizer(model, 16000)
    parts = []
    for offset in range(0, len(pcm), 8000):
        if reader.AcceptWaveform(pcm[offset:offset + 8000]):
            parts.append(json.loads(reader.Result()).get('text', ''))
    parts.append(json.loads(reader.FinalResult()).get('text', ''))
    return ' '.join(part for part in parts if part).strip()


def validate_voice(payload):
    with _lock:
        state = _session(payload.get('ticket'))
        if payload.get('consent') is not True:
            raise ValueError('A pessoa deve autorizar o cadastro da própria voz.')
        raw = identity._decode_data_url(payload.get('audio'), 'data:audio/')
        content_type = payload.get('content_type') or 'audio/webm'
        sample_index = payload.get('sample_index')
        references = state.get('voice_references', [])
        if sample_index is not None and (type(sample_index) is not int or
                not 0 <= sample_index < len(VOICE_READINGS) or sample_index > len(references)):
            raise ValueError('A etapa da leitura está incorreta.')
        heard = transcribe_reading(raw, content_type)
        coverage = reading_coverage(VOICE_READINGS[sample_index] if sample_index is not None else READING, heard)
        if coverage < MIN_READING_COVERAGE:
            raise ValueError(f'Reconheci {coverage:.0%} das palavras. O mínimo é 80%; fale as palavras do texto em qualquer ordem e tente novamente.')
        voice = identity.voice_identity_engine.embed(raw, content_type)
        if not identity._valid_embedding(voice):
            raise ValueError('Grave a leitura novamente.')
        if sample_index is not None:
            if sample_index == len(references):
                if references and identity._reference_score(voice, references) < identity.VOICE_STRONG_THRESHOLD:
                    raise ValueError('A voz ficou diferente da primeira leitura. Repita com sua voz normal.')
                state.setdefault('voice_references', []).append(voice)
            if sample_index + 1 < len(VOICE_READINGS):
                return {'ok': True, 'coverage': coverage, 'next_phrase': VOICE_READINGS[sample_index + 1]}
            state['voice'] = state['voice_references'][0]
        else:
            state.pop('voice_references', None)
            state['voice'] = voice
        return {'ok': True, 'text': heard, 'coverage': coverage}


def cancel(ticket):
    with _lock:
        if isinstance(ticket, str):
            _pending.pop(ticket, None)
    return {'ok': True}


def enroll(payload):
    with _lock:
        ticket = payload.get('ticket')
        state = _session(ticket) if ticket else None
        result = _enroll(payload, state)
        if ticket:
            _pending.pop(ticket, None)
        return result


def _enroll(payload, state=None):
    from app.services.app_lock import app_lock
    name = str(payload.get("name") or "").strip()
    password = payload.get("admin_password") or ""
    profiles = identity._read().get("profiles", [])
    if state:
        name = state['name']
        if state['admin_id'] and not any(p.get('id') == state['admin_id'] and p.get('role') == 'admin' and
                   p.get('identity_revision', 0) == state['admin_revision'] for p in profiles):
            raise ValueError('A autorização administrativa foi revogada.')
    elif not identity.authorize_management(password, [p for p in profiles if p.get('role') == 'admin']):
        raise ValueError("Informe a senha do administrador para cadastrar uma pessoa.")
    if payload.get("consent") is not True or not 2 <= len(name) <= 80:
        raise ValueError("Confirme o nome e a autorização da pessoa.")
    images = payload.get("images", [])
    modality = payload.get('modality', 'both' if images else 'voice')
    if modality not in ('voice', 'face', 'both'):
        raise ValueError('Escolha rosto, voz ou os dois.')
    if modality in ('face', 'both') and (not isinstance(images, list) or len(images) != 3):
        raise ValueError('Capture as três posições do rosto escolhido.')
    if modality == 'voice' and images:
        raise ValueError('Autorize o cadastro do rosto antes de enviar imagens.')
    if state and images and payload.get('face_consent') is not True:
        raise ValueError('Confirme separadamente o cadastro do rosto.')
    if not isinstance(images, list) or len(images) not in (0, 3):
        raise ValueError("Capture as três posições do rosto ou prossiga apenas com voz.")
    vectors, poses = [], []
    for image in images:
        detected = faces.extract(identity._decode_data_url(image, "data:image/"))
        if len(detected) != 1:
            raise ValueError("Enquadre somente a pessoa apresentada nas três posições.")
        if not identity._valid_embedding(detected[0]['embedding']) or not isinstance(detected[0]['pose'], (int, float)) or not math.isfinite(detected[0]['pose']):
            raise ValueError('Amostra de rosto inválida.')
        vectors.append(detected[0]["embedding"])
        poses.append(detected[0]["pose"])
    if poses:
        changes = sorted([poses[1] - poses[0], poses[2] - poses[0]])
        if changes[0] > -0.08 or changes[1] < 0.08:
            raise ValueError("Repita as fotos olhando para a frente, depois para cada lado.")
        if any(identity._voice_similarity(vectors[0], side) < 0.75 for side in vectors[1:]):
            raise ValueError("Os rostos diferem entre as fotos. Repita com a mesma pessoa.")
    if state and modality == 'face':
        voice = None
    elif state:
        voice = state.get('voice')
    else:
        audio = identity._decode_data_url(payload.get("audio"), "data:audio/")
        voice = identity.voice_identity_engine.embed(audio, payload.get("content_type") or "audio/webm")
    if not (state and modality == 'face') and not identity._valid_embedding(voice):
        raise ValueError("Grave a leitura novamente.")
    references = [voice] if voice else []
    if voice and state and state.get('voice_references'):
        references = state['voice_references']
        if len(references) != len(VOICE_READINGS):
            raise ValueError('Conclua as leituras da voz antes de salvar.')
    with identity._profile_lock, app_lock.mutex:
        data = identity._read()
        profiles = data.setdefault("profiles", [])
        replacing = bool(state and state.get('purpose') == 'admin_reenroll')
        admin = next((p for p in profiles if state and p.get('id') == state['admin_id'] and
                      p.get('role') == 'admin' and p.get('identity_revision', 0) == state['admin_revision']), None)
        if state and state['admin_id'] and not admin:
            raise ValueError('A autorização administrativa foi revogada. Inicie novamente.')
        creating_admin = bool(state and state.get('purpose') == 'admin_create')
        if replacing or creating_admin:
            lock_data = app_lock._read()
            if not lock_data.get('enabled') or lock_data.get('password') != state.get('unlock_password'):
                raise ValueError('A autorização administrativa foi revogada. Inicie novamente.')
            if creating_admin and any(p.get('role') == 'admin' for p in profiles):
                raise ValueError('Já existe um administrador. Inicie novamente.')
        others = [p for p in profiles if not replacing or p['id'] != admin['id']]
        if any(str(p.get("name")).casefold() == name.casefold() for p in others):
            raise ValueError("Já existe um perfil com este nome.")
        if any(identity._reference_score(ref, p.get("voice_embeddings", [])) >= 0.95 for ref in references for p in others):
            raise ValueError("Essa voz já corresponde a um perfil. Confira a pessoa apresentada.")
        if any(identity._reference_score(vector, p.get('face_embeddings_sface', [])) >= 0.95 for vector in vectors for p in others):
            raise ValueError('Este rosto já corresponde a outro perfil. Confira a pessoa apresentada.')
        if replacing:
            profile = admin
            profile.update(voice_embeddings=references, face_embeddings_sface=vectors,
                           voice_vectors=[], face_vectors=[], identity_revision=state['admin_revision'] + 1)
        else:
            profile = {"id": secrets.token_urlsafe(12), "name": name, "role": "admin" if creating_admin else "user",
                       "created_at": time.time(), "password": identity._hash_password(password or secrets.token_urlsafe(32)),
                       "voice_embeddings": references, "face_embeddings_sface": vectors}
            profiles.append(profile)
        identity._write(data)
        warning = None
        if replacing:
            old_photo = (identity.FACE_DIR / f"{profile['id']}.jpg").resolve()
            if old_photo.parent == identity.FACE_DIR.resolve():
                try:
                    old_photo.unlink(missing_ok=True)
                except OSError:
                    warning = 'Referências atualizadas, mas não foi possível remover a foto antiga do disco.'
    return {"ok": True, "profile": identity.IdentityService._public(profile), 'warning': warning}
