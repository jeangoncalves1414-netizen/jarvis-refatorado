"""Chaves no cofre do usuário do Windows; nunca inclui valores em erros/logs."""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)
_warned = False


class CredentialUnavailable(RuntimeError):
    pass


def _target(name: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_.:/-]{1,200}", name):
        raise ValueError("Nome de credencial inválido.")
    return "Jarvis/" + name


def _backend():
    try:
        import win32cred
        return win32cred
    except ImportError:
        raise CredentialUnavailable("Cofre do Windows indisponível.") from None


def warn_unavailable():
    global _warned
    if not _warned:
        logger.warning("Cofre do Windows indisponível; chaves novas permanecem no armazenamento anterior.")
        _warned = True


def save_key(name: str, value: str) -> None:
    target = _target(name)
    backend = _backend()
    try:
        backend.CredWrite({"Type": backend.CRED_TYPE_GENERIC, "TargetName": target,
                           "UserName": "Jarvis", "CredentialBlob": value,
                           "Persist": backend.CRED_PERSIST_LOCAL_MACHINE}, 0)
    except Exception:
        raise CredentialUnavailable("Não foi possível gravar no cofre do Windows.") from None


def load_key(name: str) -> str | None:
    target = _target(name)
    backend = _backend()
    try:
        record = backend.CredRead(target, backend.CRED_TYPE_GENERIC, 0)
        value = record["CredentialBlob"]
        return value.decode("utf-16-le") if isinstance(value, bytes) else value
    except Exception as exc:
        if getattr(exc, "winerror", None) == 1168:
            return None
        raise CredentialUnavailable("Não foi possível ler o cofre do Windows.") from None


def delete_key(name: str) -> None:
    target = _target(name)
    backend = _backend()
    try:
        backend.CredDelete(target, backend.CRED_TYPE_GENERIC, 0)
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1168:
            raise CredentialUnavailable("Não foi possível apagar a credencial.") from None
