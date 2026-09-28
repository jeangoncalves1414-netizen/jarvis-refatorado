from __future__ import annotations

from app.ui.panel.api import evolute


def test_sync_writes_atomically_and_advances_revision(tmp_path, monkeypatch):
    db_file = tmp_path / "lifeos_db.json"
    monkeypatch.setattr(evolute, "_get_db_file", lambda: db_file)

    status, result = evolute.handle_evolute_sync_post({
        "data": {"lifeos_habits": [{"id": "habit-1"}]},
        "updatedAt": 100,
        "baseUpdatedAt": 0,
    })

    assert status == 200
    assert result["success"] is True
    assert result["updatedAt"] >= 100
    status, stored = evolute.handle_evolute_sync_get()
    assert status == 200
    assert stored["data"]["lifeos_habits"][0]["id"] == "habit-1"


def test_sync_rejects_stale_base_revision_without_losing_server_copy(tmp_path, monkeypatch):
    db_file = tmp_path / "lifeos_db.json"
    monkeypatch.setattr(evolute, "_get_db_file", lambda: db_file)
    evolute.handle_evolute_sync_post({"data": {"lifeos_value": "server"}, "updatedAt": 500})

    status, result = evolute.handle_evolute_sync_post({
        "data": {"lifeos_value": "phone"},
        "updatedAt": 600,
        "baseUpdatedAt": 1,
    })

    assert status == 409
    assert result["conflict"] is True
    assert result["data"]["lifeos_value"] == "server"
