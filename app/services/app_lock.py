"""Local app access gate. Secrets never enter agent context or sync exports.

Biometrics are opt-in convenience: the existing local engines do not detect replay.
This gate does not encrypt files or protect against programs running as the OS user.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from http.cookies import SimpleCookie
from pathlib import Path

from app.services.identity import _hash_password, _check_password


class AppLock:
    def __init__(self, path: Path = Path('data/app_lock.json')):
        self.path = path
        self.mutex = threading.RLock()
        self.sessions: dict[str, float] = {}
        self.failures = 0
        self.retry_at = 0.0

    def _read(self):
        if not self.path.exists():
            return {}
        # A corrupt configuration must fail closed, never disable protection.
        data = json.loads(self.path.read_text(encoding='utf-8'))
        if (not isinstance(data, dict) or not isinstance(data.get('enabled'), bool)
                or (data['enabled'] and (not isinstance(data.get('password'), dict)
                    or not all(isinstance(data['password'].get(key), str) and data['password'][key] for key in ('salt', 'hash'))))):
            raise ValueError('Configuração do bloqueio inválida. Restaure um backup.')
        return data

    def _save(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix('.tmp')
        temporary.write_text(json.dumps(data), encoding='utf-8')
        temporary.replace(self.path)

    def enabled(self):
        try:
            return bool(self._read().get('enabled'))
        except (ValueError, OSError):
            return True

    def authenticated(self, cookie: str = ''):
        try:
            if not self._read().get('enabled'):
                return True
            parsed = SimpleCookie(cookie)
            token = parsed['jarvis_unlock'].value
            return self.sessions.get(token, 0) > time.monotonic()
        except Exception:
            return False

    def locked(self):
        return self.enabled() and not any(expiry > time.monotonic() for expiry in self.sessions.values())

    def lock(self):
        with self.mutex:
            self.sessions.clear()

    def status(self, cookie=''):
        data = self._read()
        return {'ok': True, 'configured': bool(data), 'enabled': bool(data.get('enabled')),
                'unlocked': self.authenticated(cookie),
                'face': bool(data.get('face')), 'voice': bool(data.get('voice'))}

    def _verify_password(self, password, data):
        if time.monotonic() < self.retry_at:
            raise ValueError('Muitas tentativas. Aguarde 30 segundos.')
        if not isinstance(password, str) or not _check_password(password, data.get('password', {})):
            self._failed()
        self.failures = 0

    def authorize_identity(self, password):
        """Use the opening password without creating or replacing an unlock session."""
        with self.mutex:
            data = self._read()
            if not data.get('enabled') or not data.get('password'):
                raise ValueError('Configure a senha de desbloqueio nas configurações antes de cadastrar o administrador.')
            self._verify_password(password, data)
            return dict(data['password'])

    def _failed(self):
        self.failures += 1
        if self.failures >= 5:
            self.retry_at = time.monotonic() + 30
            self.failures = 0
        raise ValueError('Não foi possível verificar sua identidade.')

    def _session(self):
        self.sessions.clear()
        token = secrets.token_urlsafe(32)
        self.sessions[token] = time.monotonic() + 12 * 3600
        return token

    def perform(self, payload, cookie=''):
        with self.mutex:
            data = self._read()
            action = payload.get('action')
            token = None
            if action == 'setup':
                if data:
                    raise ValueError('O bloqueio já foi configurado.')
                password = payload.get('password', '')
                if not isinstance(password, str) or not 8 <= len(password) <= 1024:
                    raise ValueError('Use uma senha de 8 a 1024 caracteres.')
                self._save({'enabled': True, 'password': _hash_password(password)})
                token = self._session()
            elif action == 'skip' and not data:
                self._save({'enabled': False})
            elif action == 'verify_password':
                self.authorize_identity(payload.get('password'))
            elif action == 'unlock':
                self._verify_password(payload.get('password'), data)
                token = self._session()
            elif action == 'biometric':
                if time.monotonic() < self.retry_at:
                    raise ValueError('Muitas tentativas. Aguarde 30 segundos.')
                kind = payload.get('kind')
                if kind not in ('face', 'voice') or not data.get(kind):
                    raise ValueError('Biometria não cadastrada.')
                vector = self._vector(kind, payload)
                from app.services.identity import _similarity, _voice_similarity, _valid_embedding
                if not _valid_embedding(vector) or not _valid_embedding(data[kind]) or len(vector) != len(data[kind]):
                    self._failed()
                score = (_voice_similarity if kind == 'voice' else _similarity)(vector, data[kind])
                if score < (0.85 if kind == 'voice' else 0.80):
                    self._failed()
                self.failures = 0
                token = self._session()
            elif action == 'lock':
                if not self.authenticated(cookie):
                    raise ValueError('Desbloqueie o app primeiro.')
                self.lock()
            elif action in ('change', 'disable', 'enroll', 'remove_biometrics'):
                if not self.authenticated(cookie):
                    raise ValueError('Desbloqueie o app primeiro.')
                if data.get('password'):
                    self._verify_password(payload.get('password'), data)
                if action == 'change':
                    password = payload.get('new_password', '')
                    if not isinstance(password, str) or not 8 <= len(password) <= 1024:
                        raise ValueError('Use uma senha de 8 a 1024 caracteres.')
                    data.update(password=_hash_password(password), enabled=True)
                elif action == 'disable':
                    data = {'enabled': False}
                elif action == 'remove_biometrics':
                    data.pop('face', None)
                    data.pop('voice', None)
                else:
                    if not data.get('enabled') or payload.get('consent') is not True:
                        raise ValueError('Ative a senha e aceite a limitação da biometria.')
                    kind = payload.get('kind')
                    if kind not in ('face', 'voice'):
                        raise ValueError('Tipo de biometria inválido.')
                    vector = self._vector(kind, payload)
                    from app.services.identity import _valid_embedding
                    if not _valid_embedding(vector):
                        raise ValueError('Amostra biométrica inválida. Grave novamente.')
                    data[kind] = vector
                self._save(data)
                token = self._session()
            else:
                raise ValueError('Operação inválida.')
            return {'ok': True}, token

    @staticmethod
    def _vector(kind, payload):
        from app.services.identity import _decode_data_url, _face_vector
        if kind == 'face':
            return _face_vector(_decode_data_url(payload.get('sample'), 'data:image/'))[0]
        from app.services.voice_identity import engine
        return engine.embed(_decode_data_url(payload.get('sample'), 'data:audio/'), payload.get('content_type', 'audio/webm'))


app_lock = AppLock()
