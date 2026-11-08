import sys
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path so tests can import the `app` package
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_sync_tombstones(tmp_path, monkeypatch):
    """Exclusões feitas em testes nunca gravam lápides em data/ do projeto."""
    monkeypatch.setattr("app.storage.sync_tombstones.TOMBSTONES_FILE", tmp_path / "sync_tombstones.json")


@pytest.fixture
def isolated_conversation_journal(tmp_path, monkeypatch):
    from app.storage.action_store import ActionStore
    monkeypatch.setattr("app.storage.task_store.TASKS_FILE", str(tmp_path / "tasks.json"))
    journal = ActionStore(tmp_path / "conversation.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", journal)
    yield
    if journal._runtime_lock:
        journal._runtime_lock.close()


def pytest_collection_modifyitems(items):
    """Keep legacy manual suites out of the default deterministic test run."""
    by_file = {
        "smoke_test.py": ("integration", "network", "hardware"),
        "stress_test.py": ("integration", "network", "hardware"),
        "test_live_server.py": ("live", "network", "hardware"),
    }
    for item in items:
        for marker in by_file.get(Path(str(item.fspath)).name, ()):
            item.add_marker(getattr(pytest.mark, marker))
