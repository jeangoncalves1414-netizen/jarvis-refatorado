"""Perfis locais de identidade para a sessão de testes do Jarvis.

O módulo não envia biometria para a nuvem. Ele guarda vetores derivados
das amostras, protegendo senhas com PBKDF2.
Os classificadores são deliberadamente conservadores: uma baixa confiança nunca
concede privilégios, apenas pede confirmação manual.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import secrets
import statistics
import threading
from functools import wraps
import time
from array import array
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.diagnostics import record as diagnostic_record
from app.services.voice_identity import VoiceIdentityError, engine as voice_identity_engine

DATA_DIR = Path("data")
_profile_lock = threading.RLock()
_password_lock = threading.Lock()
_password_failures = 0
_password_retry_at = 0.0


def _profile_update(method):
    @wraps(method)
    def update(*args, **kwargs):
        with _profile_lock:
            return method(*args, **kwargs)
    return update


IDENTITY_FILE = DATA_DIR / "identity_profiles.json"
FACE_DIR = DATA_DIR / "identity_faces"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FACE_DIR.mkdir(parents=True, exist_ok=True)

# Acesso conversacional exige correspondência forte e permissão explícita.
# Administração de permissões continua exigindo senha.
VOICE_PROBABLE_THRESHOLD = 0.70
VOICE_STRONG_THRESHOLD = 0.80


def _read() -> dict[str, Any]:
    try:
        data = json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {"profiles": []}
    except (OSError, ValueError) as exc:
        raise ValueError('Arquivo de identidade indisponível ou corrompido. Restaure um backup.') from exc
    if (not isinstance(data, dict) or not isinstance(data.get('profiles'), list)
            or any(not isinstance(p, dict) or not isinstance(p.get('id'), str)
                   or not p['id'] or not isinstance(p.get('name'), str)
                   or p.get('role', 'user') not in ('admin', 'user') for p in data['profiles'])
            or len({p['id'] for p in data['profiles']}) != len(data['profiles'])):
        raise ValueError('Arquivo de identidade inválido. Restaure um backup.')
    return data


def _write(data: dict[str, Any]) -> None:
    tmp = IDENTITY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(IDENTITY_FILE)


def _hash_password(password: str, salt: bytes | None = None) -> dict[str, str]:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240_000)
    return {"salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(digest).decode()}


def _check_password(password: str, record: dict[str, str]) -> bool:
    try:
        if not isinstance(password, str) or not 1 <= len(password) <= 1024:
            return False
        salt = base64.b64decode(record["salt"])
        expected = base64.b64decode(record["hash"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240_000)
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


def password_profile(password, profiles):
    """Share the attempt budget across all profile-password entry points."""
    global _password_failures, _password_retry_at
    with _password_lock:
        if time.monotonic() < _password_retry_at:
            raise ValueError('Muitas tentativas. Aguarde 30 segundos.')
        profile = next((p for p in profiles if _check_password(password, p.get('password', {}))), None)
        if profile:
            _password_failures = 0
        else:
            _password_failures += 1
            if _password_failures >= 5:
                _password_retry_at = time.monotonic() + 30
                _password_failures = 0
        return profile


def authorize_management(password, profiles):
    from app.services.app_lock import app_lock
    if app_lock.enabled():
        app_lock.authorize_identity(password)
        return True
    # Compatibility for installations that have never enabled the opening password.
    return bool(password_profile(password, profiles))


def _decode_data_url(value: str, accepted: str) -> bytes:
    if not isinstance(value, str) or "," not in value or not value.startswith(accepted):
        raise ValueError("Amostra inválida.")
    raw = base64.b64decode(value.split(",", 1)[1], validate=True)
    if len(raw) > 12_000_000:
        raise ValueError("Amostra muito grande.")
    return raw


def _audio_vector(raw: bytes, content_type: str = "audio/webm") -> list[float]:
    """Extrai características simples e estáveis sem guardar o áudio original."""
    samples: list[float] = []
    try:
        from pydub import AudioSegment
        fmt = "wav" if "wav" in content_type else "ogg" if "ogg" in content_type else "webm"
        segment = AudioSegment.from_file(BytesIO(raw), format=fmt).set_channels(1).set_frame_rate(8000)
        values = array("h", segment.raw_data)
        samples = [v / 32768.0 for v in values]
    except Exception:
        # O endpoint aceita WAV mesmo quando conversores externos não estão presentes.
        try:
            import wave
            with wave.open(BytesIO(raw), "rb") as wav:
                values = array("h", wav.readframes(wav.getnframes()))
                samples = [v / 32768.0 for v in values]
        except Exception as exc:
            raise ValueError("Não foi possível decodificar o áudio. Envie WAV ou permita a conversão WebM.") from exc
    if len(samples) < 160:
        raise ValueError("Áudio muito curto.")
    peak = max(abs(v) for v in samples) or 1.0
    samples = [v / peak for v in samples]
    windows = 20
    size = max(80, len(samples) // windows)
    vector: list[float] = []
    for index in range(windows):
        chunk = samples[index * size:(index + 1) * size]
        if not chunk:
            chunk = samples[-size:]
        rms = math.sqrt(sum(v * v for v in chunk) / len(chunk))
        crossings = sum(1 for a, b in zip(chunk, chunk[1:]) if (a < 0) != (b < 0)) / len(chunk)
        vector.extend((round(rms, 6), round(crossings, 6)))
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _face_vector(raw: bytes) -> tuple[list[float], bytes]:
    from app.services.face_identity import engine
    return engine.embed(raw), raw


def _similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        return 0.0
    distance = math.sqrt(sum((a - b) ** 2 for a, b in zip(left, right)))
    return max(0.0, min(1.0, 1.0 - distance / math.sqrt(2.0)))


def _voice_similarity(left: list[float], right: list[float]) -> float:
    """Score de voz na mesma escala [0, 1] usada pelo WeSpeaker.

    Embeddings de locutor são comparados por cosseno. A antiga conversão por
    distância fazia uma amostra com cosseno 0,73 parecer confiança 0,48 e
    rejeitava a própria pessoa mesmo com gravações consistentes.
    """
    if len(left) != len(right) or not left:
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left)) * math.sqrt(sum(value * value for value in right))
    if not denominator:
        return 0.0
    cosine = sum(a * b for a, b in zip(left, right)) / denominator
    return max(0.0, min(1.0, (cosine + 1.0) / 2.0))


def _valid_embedding(vector):
    return (isinstance(vector, (list, tuple)) and bool(vector)
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in vector)
            and any(vector))


def _reference_score(vector, references):
    scores = [_voice_similarity(vector, saved) for saved in references
              if _valid_embedding(saved) and len(saved) == len(vector)]
    # One accidentally enrolled outlier must not outweigh consistent references.
    return statistics.median(scores) if scores else 0.0


def _match_voice(vector, profiles, *, field="voice_embeddings", threshold=VOICE_PROBABLE_THRESHOLD):
    """Reject ambiguous identities; similarity is not a calibrated probability."""
    ranked = []
    valid = _valid_embedding(vector)
    for profile in profiles if valid else []:
        score = _reference_score(vector, profile.get(field, []))
        if score:
            ranked.append((score, profile))
    ranked.sort(key=lambda item: item[0], reverse=True)
    score = ranked[0][0] if ranked else 0.0
    margin = score - ranked[1][0] if len(ranked) > 1 else score
    # shortcut: conservative uncalibrated margin; calibrate with household recordings.
    ambiguous = len(ranked) > 1 and margin < 0.08
    matched = bool(valid and ranked and score >= threshold and not ambiguous)
    return {"ok": True, "matched": matched, "confidence": round(score, 3),
            "score_kind": "similarity", "margin": round(margin, 3),
            "reason": "ambiguous" if ambiguous else "matched" if matched else "unknown",
            "profile": IdentityService._public(ranked[0][1]) if matched else None,
            "requires_confirmation": not matched or score < VOICE_STRONG_THRESHOLD}


class IdentityService:
    @staticmethod
    def profile_exists(profile_id: str) -> bool:
        """Confere se um id pertence a um perfil local cadastrado."""
        return any(p.get("id") == str(profile_id or "") for p in _read().get("profiles", []))

    @staticmethod
    def authenticate(profile_id: str, password: str) -> bool:
        """Autentica uma operacao manual sem expor o hash da senha."""
        profiles = [p for p in _read().get('profiles', []) if p.get('id') == str(profile_id or '')]
        return bool(profiles and authorize_management(password, profiles))

    @staticmethod
    def status() -> dict[str, Any]:
        profiles = _read().get("profiles", [])
        return {"ok": True, "profiles": [IdentityService._public(p) for p in profiles], "has_admin": any(p.get("role") == "admin" for p in profiles)}

    @staticmethod
    def _public(profile: dict[str, Any]) -> dict[str, Any]:
        return {"id": profile.get("id"), "name": profile.get("name"), "role": profile.get("role", "user"), "voice_samples": len(profile.get("voice_embeddings", [])), "legacy_voice_samples": len(profile.get("voice_vectors", [])), "face_samples": len(profile.get("face_embeddings_sface", [])), "legacy_face_samples": len(profile.get("face_vectors", [])), "created_at": profile.get("created_at"), "permissions": profile.get("permissions", []), "command_level": profile.get("command_level", "visitor"), "identity_revision": profile.get("identity_revision", 0)}

    @staticmethod
    def voice_model_status() -> dict[str, Any]:
        return voice_identity_engine.status()

    @staticmethod
    def install_voice_model() -> dict[str, Any]:
        try:
            return {"ok": True, **voice_identity_engine.install_model()}
        except VoiceIdentityError as exc:
            return {"ok": False, "error": str(exc)}

    @staticmethod
    @_profile_update
    def enroll_admin(name: str, password: str) -> dict[str, Any]:
        name = str(name or "").strip()[:80]
        if len(name) < 2 or not isinstance(password, str) or not 8 <= len(password) <= 1024:
            return {"ok": False, "error": "Informe um nome e uma senha com pelo menos 8 caracteres."}
        data = _read()
        from app.services.app_lock import app_lock
        if app_lock.enabled():
            app_lock.authorize_identity(password)
        if data.get('profiles'):
            return {"ok": False, "error": "Já existe um administrador. Use a senha do administrador para adicionar outro perfil."}
        profile = {"id": secrets.token_urlsafe(12), "name": name, "role": "admin", "created_at": time.time(), "password": _hash_password(password), "voice_vectors": [], "face_vectors": []}
        data.setdefault("profiles", []).append(profile)
        _write(data)
        return {"ok": True, "profile": IdentityService._public(profile)}

    @staticmethod
    @_profile_update
    def enroll_profile(name: str, role: str, admin_password: str) -> dict[str, Any]:
        """Cria uma pessoa comum somente após autenticação do administrador."""
        name = str(name or "").strip()[:80]
        data = _read()
        admin = authorize_management(admin_password, [p for p in data.get('profiles', []) if p.get('role') == 'admin'])
        if not admin:
            return {"ok": False, "error": "Senha do administrador inválida."}
        if len(name) < 2:
            return {"ok": False, "error": "Informe um nome para o perfil."}
        if any(p.get('name', '').casefold() == name.casefold() for p in data['profiles']):
            return {'ok': False, 'error': 'Já existe um perfil com este nome.'}
        profile = {"id": secrets.token_urlsafe(12), "name": name, "role": "user", "created_at": time.time(), "password": _hash_password(secrets.token_urlsafe(32)), "voice_vectors": [], "face_vectors": []}
        data.setdefault("profiles", []).append(profile)
        _write(data)
        return {"ok": True, "profile": IdentityService._public(profile)}

    @staticmethod
    @_profile_update
    def add_sample(profile_id: str, password: str, kind: str, sample: str, content_type: str = "") -> dict[str, Any]:
        data = _read()
        profile = next((p for p in data.get("profiles", []) if p.get("id") == profile_id), None)
        authorized = authorize_management(password, [p for p in data.get('profiles', [])
                                                if p.get('id') == profile_id or p.get('role') == 'admin'])
        if not profile or not authorized:
            return {"ok": False, "error": "Perfil ou senha inválidos."}
        if kind == "voice":
            raw = _decode_data_url(sample, "data:audio/")
            try:
                embedding = voice_identity_engine.embed(raw, content_type or "audio/webm")
            except VoiceIdentityError as exc:
                diagnostic_record("voice.identity", "enrollment_audio_failed", "WARN", reason=str(exc), content_type=content_type or "audio/webm")
                return {"ok": False, "error": str(exc)}
            if not _valid_embedding(embedding):
                return {"ok": False, "error": "A amostra de voz retornou uma impressão inválida. Grave novamente."}
            references = profile.get("voice_embeddings", [])
            if references and _reference_score(embedding, references) < VOICE_STRONG_THRESHOLD:
                return {"ok": False, "error": "Esta voz difere das referências deste perfil. Confirme a pessoa selecionada e grave novamente em um ambiente silencioso."}
            for other in data.get("profiles", []):
                if other.get("id") != profile_id and _reference_score(embedding, other.get("voice_embeddings", [])) >= 0.95:
                    return {"ok": False, "error": "A amostra ficou muito semelhante à voz de outro perfil. Confirme quem está falando antes de cadastrar."}
            profile.setdefault("voice_embeddings", []).append(embedding)
        elif kind == "face":
            raw = _decode_data_url(sample, "data:image/")
            vector, _ = _face_vector(raw)
            if not _valid_embedding(vector):
                return {'ok': False, 'error': 'Amostra de rosto inválida.'}
            if profile.get('face_embeddings_sface') and _reference_score(vector, profile['face_embeddings_sface']) < VOICE_STRONG_THRESHOLD:
                return {'ok': False, 'error': 'Este rosto difere das referências deste perfil.'}
            if any(p.get('id') != profile_id and _reference_score(vector, p.get('face_embeddings_sface', [])) >= 0.95 for p in data['profiles']):
                return {'ok': False, 'error': 'Este rosto já corresponde a outro perfil.'}
            profile.setdefault("face_embeddings_sface", []).append(vector)
        else:
            return {"ok": False, "error": "Tipo de amostra inválido."}
        _write(data)
        return {"ok": True, "profile": IdentityService._public(profile)}

    @staticmethod
    def verify(kind: str, sample: str, content_type: str = "") -> dict[str, Any]:
        try:
            if kind == "voice":
                vector = voice_identity_engine.embed(_decode_data_url(sample, "data:audio/"), content_type or "audio/webm")
                field = "voice_embeddings"
            elif kind == "face":
                vector, _ = _face_vector(_decode_data_url(sample, "data:image/"))
                field = "face_embeddings_sface"
            else:
                return {"ok": False, "error": "Tipo de verificação inválido."}
        except ValueError as exc:
            diagnostic_record("voice.identity", "verification_failed", "WARN", kind=kind, reason=str(exc))
            return {"ok": False, "error": str(exc)}
        if kind == "voice":
            return _match_voice(vector, _read().get("profiles", []))
        return _match_voice(vector, _read().get("profiles", []), field="face_embeddings_sface", threshold=0.75)

    @staticmethod
    def identify_audio_bytes(raw: bytes, content_type: str = "audio/webm") -> dict[str, Any]:
        """Mede a identidade da fala; a política de acesso é avaliada separadamente."""
        if not any(profile.get("voice_embeddings") for profile in _read().get("profiles", [])):
            return {"ok": True, "enabled": False}
        try:
            vector = voice_identity_engine.embed(raw, content_type)
        except VoiceIdentityError as exc:
            diagnostic_record("voice.identity", "turn_identification_failed", "WARN", reason=str(exc), content_type=content_type)
            return {"ok": False, "enabled": True, "error": str(exc)}
        return {**_match_voice(vector, _read().get("profiles", [])), "enabled": True}
