"""Perfis locais de identidade para a sessão de testes do Jarvis.

O módulo não envia biometria para a nuvem. Ele guarda somente vetores derivados
das amostras e uma imagem de referência opcional, protegendo senhas com PBKDF2.
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
import time
from array import array
from io import BytesIO
from pathlib import Path
from typing import Any

from app.core.diagnostics import record as diagnostic_record
from app.services.voice_identity import VoiceIdentityError, engine as voice_identity_engine

DATA_DIR = Path("data")
IDENTITY_FILE = DATA_DIR / "identity_profiles.json"
FACE_DIR = DATA_DIR / "identity_faces"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FACE_DIR.mkdir(parents=True, exist_ok=True)

# A voz identifica contexto, nunca autentica operações sensíveis. Mantemos duas
# faixas: provável para a conversa, forte para uma confirmação visual/manual.
VOICE_PROBABLE_THRESHOLD = 0.70
VOICE_STRONG_THRESHOLD = 0.80


def _read() -> dict[str, Any]:
    try:
        return json.loads(IDENTITY_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"profiles": []}


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
        salt = base64.b64decode(record["salt"])
        expected = base64.b64decode(record["hash"])
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240_000)
        return secrets.compare_digest(actual, expected)
    except Exception:
        return False


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
    try:
        from PIL import Image
        import cv2
        import numpy as np
        image = Image.open(BytesIO(raw)).convert("RGB")
        pixels = np.array(image)
        gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
        cascade = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        faces = cv2.CascadeClassifier(cascade).detectMultiScale(gray, 1.1, 5, minSize=(60, 60))
        if not len(faces):
            raise ValueError("Nenhum rosto frontal suficientemente visível foi encontrado. Aproxime-se e olhe para a câmera.")
        x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
        # Margem e equalização tornam o vetor menos sensível a pequenos
        # deslocamentos, iluminação e cortes diferentes da câmera.
        margin_x, margin_y = int(w * 0.16), int(h * 0.20)
        x1, y1 = max(0, x - margin_x), max(0, y - margin_y)
        x2, y2 = min(gray.shape[1], x + w + margin_x), min(gray.shape[0], y + h + margin_y)
        gray = cv2.equalizeHist(gray[y1:y2, x1:x2])
        resized = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype("float32") / 255.0
        vector = resized.flatten().tolist()
        mean = sum(vector) / len(vector)
        vector = [v - mean for v in vector]
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector], raw
    except Exception as exc:
        raise ValueError("Não foi possível processar a imagem. Instale Pillow e OpenCV.") from exc


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


class IdentityService:
    @staticmethod
    def profile_exists(profile_id: str) -> bool:
        """Confere se um id pertence a um perfil local cadastrado."""
        return any(p.get("id") == str(profile_id or "") for p in _read().get("profiles", []))

    @staticmethod
    def authenticate(profile_id: str, password: str) -> bool:
        """Autentica uma operacao manual sem expor o hash da senha."""
        profile = next((p for p in _read().get("profiles", []) if p.get("id") == str(profile_id or "")), None)
        return bool(profile and _check_password(password or "", profile.get("password", {})))

    @staticmethod
    def status() -> dict[str, Any]:
        profiles = _read().get("profiles", [])
        return {"ok": True, "profiles": [IdentityService._public(p) for p in profiles], "has_admin": any(p.get("role") == "admin" for p in profiles)}

    @staticmethod
    def _public(profile: dict[str, Any]) -> dict[str, Any]:
        return {"id": profile.get("id"), "name": profile.get("name"), "role": profile.get("role", "user"), "voice_samples": len(profile.get("voice_embeddings", [])), "legacy_voice_samples": len(profile.get("voice_vectors", [])), "face_samples": len(profile.get("face_vectors", [])), "created_at": profile.get("created_at")}

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
    def enroll_admin(name: str, password: str) -> dict[str, Any]:
        name = str(name or "").strip()[:80]
        if len(name) < 2 or len(password or "") < 8:
            return {"ok": False, "error": "Informe um nome e uma senha com pelo menos 8 caracteres."}
        data = _read()
        admins = [p for p in data.get("profiles", []) if p.get("role") == "admin"]
        if admins:
            return {"ok": False, "error": "Já existe um administrador. Use a senha do administrador para adicionar outro perfil."}
        profile = {"id": secrets.token_urlsafe(12), "name": name, "role": "admin", "created_at": time.time(), "password": _hash_password(password), "voice_vectors": [], "face_vectors": []}
        data.setdefault("profiles", []).append(profile)
        _write(data)
        return {"ok": True, "profile": IdentityService._public(profile)}

    @staticmethod
    def enroll_profile(name: str, role: str, admin_password: str) -> dict[str, Any]:
        """Cria uma pessoa comum somente após autenticação do administrador."""
        name = str(name or "").strip()[:80]
        data = _read()
        admin = next((p for p in data.get("profiles", []) if p.get("role") == "admin"), None)
        if not admin or not _check_password(admin_password or "", admin.get("password", {})):
            return {"ok": False, "error": "Senha do administrador inválida."}
        if len(name) < 2:
            return {"ok": False, "error": "Informe um nome para o perfil."}
        profile = {"id": secrets.token_urlsafe(12), "name": name, "role": "user" if role not in {"admin", "user"} else role, "created_at": time.time(), "password": _hash_password(admin_password), "voice_vectors": [], "face_vectors": []}
        data.setdefault("profiles", []).append(profile)
        _write(data)
        return {"ok": True, "profile": IdentityService._public(profile)}

    @staticmethod
    def add_sample(profile_id: str, password: str, kind: str, sample: str, content_type: str = "") -> dict[str, Any]:
        data = _read()
        profile = next((p for p in data.get("profiles", []) if p.get("id") == profile_id), None)
        if not profile or not _check_password(password or "", profile.get("password", {})):
            return {"ok": False, "error": "Perfil ou senha inválidos."}
        if kind == "voice":
            raw = _decode_data_url(sample, "data:audio/")
            try:
                embedding = voice_identity_engine.embed(raw, content_type or "audio/webm")
            except VoiceIdentityError as exc:
                diagnostic_record("voice.identity", "enrollment_audio_failed", "WARN", reason=str(exc), content_type=content_type or "audio/webm")
                return {"ok": False, "error": str(exc)}
            profile.setdefault("voice_embeddings", []).append(embedding)
        elif kind == "face":
            raw = _decode_data_url(sample, "data:image/")
            vector, _ = _face_vector(raw)
            profile.setdefault("face_vectors", []).append(vector)
            (FACE_DIR / f"{profile_id}.jpg").write_bytes(raw)
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
                field = "face_vectors"
            else:
                return {"ok": False, "error": "Tipo de verificação inválido."}
        except ValueError as exc:
            diagnostic_record("voice.identity", "verification_failed", "WARN", kind=kind, reason=str(exc))
            return {"ok": False, "error": str(exc)}
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        for profile in _read().get("profiles", []):
            for saved in profile.get(field, []):
                score = _voice_similarity(vector, saved) if kind == "voice" else _similarity(vector, saved)
                if score > best[0]:
                    best = (score, profile)
        # Threshold alto: falhar com segurança é preferível a identificar a pessoa errada.
        threshold = VOICE_PROBABLE_THRESHOLD if kind == "voice" else 0.64
        matched = best[1] if best[0] >= threshold else None
        requires_confirmation = bool(kind == "voice" and matched and best[0] < VOICE_STRONG_THRESHOLD)
        diagnostic_record("voice.identity", "verification_scored", "INFO", kind=kind, confidence=round(best[0], 3), matched=bool(matched), requires_confirmation=requires_confirmation)
        return {"ok": True, "matched": bool(matched), "confidence": round(best[0], 3), "profile": IdentityService._public(matched) if matched else None, "requires_confirmation": requires_confirmation or bool(best[1] and not matched)}

    @staticmethod
    def identify_audio_bytes(raw: bytes, content_type: str = "audio/webm") -> dict[str, Any]:
        """Identifica somente a fala do turno; nunca ativa um perfil ou permissões."""
        if not any(profile.get("voice_embeddings") for profile in _read().get("profiles", [])):
            return {"ok": True, "enabled": False}
        try:
            vector = voice_identity_engine.embed(raw, content_type)
        except VoiceIdentityError as exc:
            diagnostic_record("voice.identity", "turn_identification_failed", "WARN", reason=str(exc), content_type=content_type)
            return {"ok": False, "enabled": True, "error": str(exc)}
        best: tuple[float, dict[str, Any] | None] = (0.0, None)
        for profile in _read().get("profiles", []):
            for saved in profile.get("voice_embeddings", []):
                score = _voice_similarity(vector, saved)
                if score > best[0]:
                    best = (score, profile)
        matched = best[1] if best[0] >= VOICE_PROBABLE_THRESHOLD else None
        requires_confirmation = bool(matched and best[0] < VOICE_STRONG_THRESHOLD)
        return {"ok": True, "enabled": True, "matched": bool(matched), "confidence": round(best[0], 3), "profile": IdentityService._public(matched) if matched else None, "requires_confirmation": requires_confirmation or bool(best[1] and not matched)}
