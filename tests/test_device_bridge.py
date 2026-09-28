from __future__ import annotations

from app.services.device_bridge import DeviceBridgeService


def test_pairing_requires_code_and_never_reveals_secrets(tmp_path) -> None:
    service = DeviceBridgeService(tmp_path / "bridge.json")
    code = service._read()["pairing_code"]
    assert not service.register_device("phone")["ok"]
    assert not service.register_device("phone", pairing_code="wrong")["ok"]
    paired = service.register_device("phone", kind="controller", pairing_code=code)
    assert paired["ok"] and paired["device_token"]
    assert "pairing_code" not in paired
    status = service.get_status()
    assert code not in str(status) and paired["device_token"] not in str(status)
    assert not service.heartbeat("phone")["ok"]
    assert service.heartbeat("phone", paired["device_token"])["ok"]
    assert service.remove_device("phone", paired["device_token"])
    assert not service.heartbeat("phone", paired["device_token"])["ok"]


def test_command_requires_known_authorized_source_and_target(tmp_path) -> None:
    service = DeviceBridgeService(tmp_path / "bridge.json")
    code = service._read()["pairing_code"]
    source = service.register_device("desktop", kind="controller", pairing_code=code)
    service.register_device("lamp", kind="controller", pairing_code=code)
    assert not service.command("lamp", "turn_on", source="unknown", device_token=source["device_token"])["ok"]
    assert service.command("lamp", "turn_on", source="desktop", device_token=source["device_token"])["ok"]
