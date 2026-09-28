"""Local device bridge used by the desktop panel and future mobile clients.

This module deliberately does not pretend to speak the Smart Life protocol yet.
It provides the stable, provider-agnostic contract that both clients will use:
pair a device, observe its connection and send a normalized command.  A real
Tuya/Smart Life adapter can be plugged in later without changing the UI or the
mobile protocol.
"""
from __future__ import annotations

import json
import secrets
import hashlib
import hmac
import threading
import time
from pathlib import Path
from typing import Any


class DeviceBridgeService:
    """Persisted registry and command bus for Jarvis-compatible clients."""

    _lock = threading.RLock()

    def __init__(self, state_path: str | Path = "data/device_bridge.json") -> None:
        # O app pode ser iniciado por atalho, terminal ou pelo tray, cada um
        # com um diretório de trabalho diferente. O registro do pareamento deve
        # apontar sempre para o mesmo arquivo do projeto.
        if str(state_path).replace("\\", "/") == "data/device_bridge.json":
            self.state_path = Path(__file__).resolve().parents[2] / "data" / "device_bridge.json"
        else:
            self.state_path = Path(state_path)

    def _default_state(self) -> dict[str, Any]:
        return {
            "version": 1,
            "pairing_code": secrets.token_urlsafe(6).upper(),
            "devices": [],
            "events": [],
        }

    def _read(self) -> dict[str, Any]:
        created = False
        try:
            raw = json.loads(self.state_path.read_text(encoding="utf-8"))
            state = self._default_state()
            if isinstance(raw, dict):
                state.update(raw)
            if not isinstance(state.get("devices"), list):
                state["devices"] = []
            if not isinstance(state.get("events"), list):
                state["events"] = []
            # Um arquivo vazio/corrompido também precisa voltar a um estado
            # estável; caso contrário cada refresh poderia gerar um código.
            if not isinstance(raw, dict) or not state.get("pairing_code"):
                state["pairing_code"] = self._default_state()["pairing_code"]
                created = True
        except FileNotFoundError:
            state = self._default_state()
            created = True
        except (OSError, ValueError, json.JSONDecodeError):
            state = self._default_state()
            created = True

        if created:
            try:
                self._write(state)
            except OSError:
                # A falha de disco não impede a API de responder; o próximo
                # ciclo tentará persistir novamente.
                pass
        return state

    def _write(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _now() -> float:
        return time.time()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            state = self._read()
            now = self._now()
            devices = []
            for device in state["devices"]:
                item = self._public_device(device)
                # A client that stopped heartbeating is shown as offline.  This
                # keeps the PC and the future phone UI consistent after sleep.
                last_seen = float(item.get("last_seen") or 0)
                is_simulator = item.get("platform") == "simulator" or item.get("transport") == "simulator"
                item["connected"] = is_simulator or (bool(item.get("connected")) and now - last_seen <= 45)
                devices.append(item)
            return {
                "ok": True,
                "protocol": "jarvis-bridge-v1",
                "devices": devices,
                "events": [self._public_event(event) for event in state["events"][-30:]],
            }

    def get_pairing_code(self) -> str:
        """Return the temporary pairing code only to an authenticated control UI."""
        with self._lock:
            return str(self._read()["pairing_code"])

    def register_device(
        self,
        device_id: Any,
        name: Any = "Dispositivo",
        kind: Any = "client",
        platform: Any = "unknown",
        transport: Any = "lan",
        pairing_code: Any = None,
    ) -> dict[str, Any]:
        device_id = str(device_id or "").strip()
        if not device_id:
            return {"ok": False, "error": "device_id é obrigatório."}
        with self._lock:
            state = self._read()
            now = self._now()
            current = next((item for item in state["devices"] if item.get("id") == device_id), None)
            if current is None:
                if not pairing_code or not hmac.compare_digest(str(pairing_code).strip().upper(), str(state["pairing_code"]).upper()):
                    return {"ok": False, "error": "Código de pareamento obrigatório ou inválido."}
                current = {"id": device_id}
                state["devices"].append(current)
                device_token = secrets.token_urlsafe(32)
                current["token_verifier"] = self._token_verifier(device_token)
                current["permissions"] = self._default_permissions(kind)
            else:
                return {"ok": False, "error": "Dispositivo já pareado; use sua credencial de dispositivo."}
            current.update({
                "name": str(name or current.get("name") or "Dispositivo"),
                "kind": str(kind or current.get("kind") or "client"),
                "platform": str(platform or current.get("platform") or "unknown"),
                "transport": str(transport or current.get("transport") or "lan"),
                "connected": True,
                "last_seen": now,
            })
            self._append_event(state, "device.connected", device_id, {"name": current["name"]})
            self._write(state)
            return {"ok": True, "device": self._public_device(current), "device_token": device_token}

    def heartbeat(self, device_id: Any, device_token: Any = None) -> dict[str, Any]:
        device_id = str(device_id or "").strip()
        with self._lock:
            state = self._read()
            current = next((item for item in state["devices"] if item.get("id") == device_id), None)
            if current is None:
                return {"ok": False, "error": "Dispositivo não pareado."}
            if not self._valid_token(current, device_token):
                return {"ok": False, "error": "Credencial do dispositivo inválida."}
            current["connected"] = True
            current["last_seen"] = self._now()
            self._write(state)
            return {"ok": True, "device": self._public_device(current)}

    def command(self, target_id: Any, command: Any, payload: Any = None, source: Any = "desktop", device_token: Any = None) -> dict[str, Any]:
        target_id = str(target_id or "").strip()
        command = str(command or "").strip()
        if not target_id or not command:
            return {"ok": False, "error": "target_id e command são obrigatórios."}
        payload = payload if isinstance(payload, dict) else {}
        with self._lock:
            state = self._read()
            device = next((item for item in state["devices"] if item.get("id") == target_id), None)
            source_device = next((item for item in state["devices"] if item.get("id") == str(source)), None)
            if device is None or source_device is None:
                return {"ok": False, "error": "Dispositivo não encontrado."}
            if not self._valid_token(source_device, device_token):
                return {"ok": False, "error": "Credencial do dispositivo inválida."}
            if "command" not in source_device.get("permissions", []) or "receive_command" not in device.get("permissions", []):
                return {"ok": False, "error": "Permissão command não concedida."}
            # Normalized state is useful for the simulator and harmless for a
            # future adapter, which can consume the same event downstream.
            if command in {"turn_on", "turn_off"}:
                device["power"] = command == "turn_on"
            elif command in {"set_brightness", "set_color", "set_temperature"}:
                device[command.removeprefix("set_")] = payload.get("value", payload)
            device["last_seen"] = self._now()
            device["connected"] = True
            event = self._append_event(state, f"device.{command}", target_id, {"source": source, **payload})
            event["status"] = "executed"
            self._write(state)
            return {"ok": True, "accepted": True, "executed": True, "device": self._public_device(device), "event": self._public_event(event)}

    def remove_device(self, device_id: Any, device_token: Any = None) -> bool:
        device_id = str(device_id or "").strip()
        with self._lock:
            state = self._read()
            current = next((item for item in state["devices"] if item.get("id") == device_id), None)
            if current is None or not self._valid_token(current, device_token):
                return False
            before = len(state["devices"])
            state["devices"] = [item for item in state["devices"] if item.get("id") != device_id]
            changed = len(state["devices"]) != before
            if changed:
                self._append_event(state, "device.removed", device_id, {})
                self._write(state)
            return changed

    @staticmethod
    def _append_event(state: dict[str, Any], event_type: str, device_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        event = {"id": secrets.token_hex(5), "type": event_type, "device_id": device_id, "payload": payload, "at": time.time()}
        state["events"].append(event)
        del state["events"][:-100]
        return event

    @staticmethod
    def _token_verifier(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _valid_token(self, device: dict[str, Any], token: Any) -> bool:
        value = str(token or "")
        verifier = str(device.get("token_verifier") or "")
        return bool(value and verifier and hmac.compare_digest(self._token_verifier(value), verifier))

    @staticmethod
    def _default_permissions(kind: Any) -> list[str]:
        if str(kind).lower() in {"desktop", "controller", "client"}:
            return ["status", "notify", "command", "receive_command"]
        return ["status", "notify", "receive_command"]

    @staticmethod
    def _public_device(device: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in device.items() if key not in {"token_verifier", "pairing_code", "device_token"}}

    @staticmethod
    def _public_event(event: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in event.items() if key not in {"token", "secret", "pairing_code", "device_token"}}
