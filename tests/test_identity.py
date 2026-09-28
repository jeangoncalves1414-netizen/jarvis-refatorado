from pathlib import Path

from app.services import identity


def test_identity_admin_and_profile_are_password_protected(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "IDENTITY_FILE", Path(tmp_path) / "profiles.json")
    monkeypatch.setattr(identity, "FACE_DIR", Path(tmp_path) / "faces")
    identity.FACE_DIR.mkdir()

    first = identity.IdentityService.enroll_admin("Jean", "01020304")
    assert first["ok"] is True
    profile_id = first["profile"]["id"]
    assert identity.IdentityService.enroll_admin("Outro", "01020304")["ok"] is False
    assert identity.IdentityService.enroll_profile("Visitante", "user", "errada")["ok"] is False
    visitor = identity.IdentityService.enroll_profile("Visitante", "user", "01020304")
    assert visitor["ok"] is True
    assert identity.IdentityService.add_sample(profile_id, "errada", "face", "data:image/jpeg;base64,AA==")["ok"] is False


def test_password_hash_is_not_plaintext(tmp_path, monkeypatch):
    monkeypatch.setattr(identity, "IDENTITY_FILE", Path(tmp_path) / "profiles.json")
    result = identity.IdentityService.enroll_admin("Jean", "01020304")
    stored = (Path(tmp_path) / "profiles.json").read_text(encoding="utf-8")
    assert result["ok"] is True
    assert "01020304" not in stored
