import json

import pytest

from app.storage import credential_store as vault, runtime_settings as rs


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "runtime_settings.json"
    monkeypatch.setattr(rs, "RUNTIME_SETTINGS_FILE", str(path))
    return path


def test_legacy_keys_migrate_and_remain_available_for_sync(settings_file, isolated_credentials):
    settings_file.write_text(json.dumps({"api_keys": {"groq": "fake-a,fake-b", "gemini": "fake-c"}, "llm_provider": "groq"}))
    data = rs._read()
    assert data["api_keys"] == {"groq": "fake-a,fake-b", "gemini": "fake-c"}
    assert "fake-" not in settings_file.read_text()
    assert len(isolated_credentials) == 3
    assert "_credential_refs" not in rs.flatten_settings(data)
    assert rs.flatten_settings(data)["api_keys.groq"] == "fake-a,fake-b"
    rs.set_llm_provider("gemini")
    assert rs._read()["api_keys"]["groq"] == "fake-a,fake-b"
    rs.set_api_keys({"groq": ""})
    assert rs._read()["api_keys"]["groq"] == ""


def test_unavailable_vault_keeps_legacy_values(settings_file, monkeypatch, caplog):
    def unavailable(*args):
        raise vault.CredentialUnavailable()
    monkeypatch.setattr(vault, "save_key", unavailable)
    monkeypatch.setattr(vault, "_warned", False)
    settings_file.write_text(json.dumps({"api_keys": {"fish": "fake-secret"}}))
    assert rs._read()["api_keys"]["fish"] == "fake-secret"
    assert json.loads(settings_file.read_text())["api_keys"]["fish"] == "fake-secret"
    assert "indisponível" in caplog.text and "fake-secret" not in caplog.text


def test_unavailable_vault_does_not_erase_references(settings_file, monkeypatch):
    settings_file.write_text(json.dumps({"api_keys": {"oxyy": "fake-secret"}}))
    rs._read()
    references = json.loads(settings_file.read_text())["api_keys"]
    def unavailable(*args):
        raise vault.CredentialUnavailable()
    monkeypatch.setattr(vault, "load_key", unavailable)
    rs.set_llm_provider("groq")
    assert json.loads(settings_file.read_text())["api_keys"] == references
