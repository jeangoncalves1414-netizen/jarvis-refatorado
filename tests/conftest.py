import sys
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path so tests can import the `app` package
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def isolated_persona(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_DATA_DIR", str(tmp_path / "persona"))


@pytest.fixture(autouse=True)
def isolated_sync_tombstones(tmp_path, monkeypatch):
    """Exclusões feitas em testes nunca gravam lápides em data/ do projeto."""
    monkeypatch.setattr("app.storage.sync_tombstones.TOMBSTONES_FILE", tmp_path / "sync_tombstones.json")


@pytest.fixture(autouse=True)
def isolated_auto_approvals(tmp_path, monkeypatch):
    """Regras e Modo liberado de teste nunca leem nem gravam data/auto_approvals.json do projeto."""
    from app.storage.auto_approvals import AutoApprovalStore
    store = AutoApprovalStore(str(tmp_path / "auto_approvals.json"))
    for module in ("app.storage.auto_approvals", "app.agent.action_executor", "app.ui.panel.api.approvals"):
        monkeypatch.setattr(f"{module}.auto_approvals", store)
    return store


@pytest.fixture(autouse=True)
def isolated_routines(tmp_path, monkeypatch):
    """Rotinas e histórico de teste nunca gravam data/routines.sqlite3 do projeto."""
    from app.storage.routine_store import RoutineStore
    store = RoutineStore(tmp_path / "routines.sqlite3")
    monkeypatch.setattr("app.storage.routine_store.routine_store", store)
    return store


@pytest.fixture(autouse=True)
def effect_checks_off(monkeypatch):
    """Verificação de efeito (processos e janelas reais) fica desligada; os testes dela ligam com sondas falsas."""
    monkeypatch.setattr("app.agent.effect_checks.enabled", False)


@pytest.fixture
def isolated_conversation_journal(tmp_path, monkeypatch):
    from app.storage.action_store import ActionStore
    monkeypatch.setattr("app.storage.task_store.TASKS_FILE", str(tmp_path / "tasks.json"))
    journal = ActionStore(tmp_path / "conversation.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", journal)
    yield
    if journal._runtime_lock:
        journal._runtime_lock.close()


@pytest.fixture
def isolated_lote6_data(tmp_path, monkeypatch):
    """Dados pessoais, cofre, configurações, aprovações e Central em tmp (lote 6).

    Nada escreve em data/ do projeto nem em ~/Documents/Evolute: o cwd vai para tmp
    (CalendarService usa data/calendar.json relativo) e os caminhos fixos são trocados.
    """
    from types import SimpleNamespace

    from app.services import finance, habits, memory_vault, tasks
    from app.storage.action_store import ActionStore
    from app.storage.auto_approvals import AutoApprovalStore

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    monkeypatch.setattr(habits, "DB_PATH", tmp_path / "data" / "lifestyle.db")
    habits.init_db()
    tasks.init_task_tables()
    finance.init_finance_tables()

    lifeos_db = tmp_path / "lifeos" / "lifeos_db.json"
    monkeypatch.setattr("app.services.lifeos._DOCUMENTS_DB", lifeos_db)
    monkeypatch.setattr("app.services.lifeos._LOCAL_DB", lifeos_db)
    monkeypatch.setattr('app.ui.panel.api.evolute._LOCAL_DB', lifeos_db)
    monkeypatch.setattr('app.ui.panel.api.evolute._DOCUMENTS_DB', lifeos_db)

    vault = tmp_path / "vault"
    monkeypatch.setattr(memory_vault, "VAULT_DIR", vault)
    monkeypatch.setattr(memory_vault, "DAILY_NOTES_DIR", vault / "01-Daily-Notes")
    monkeypatch.setattr(memory_vault, "PROFILE_DIR", vault / "02-User-Profile")
    monkeypatch.setattr(memory_vault, "PRIMING_DIR", vault / "03-Priming-Notes")
    monkeypatch.setattr(memory_vault, "PROJECTS_DIR", vault / "04-Projects")
    monkeypatch.setattr(memory_vault, "PROFILE_FILE", vault / "02-User-Profile" / "USER-PROFILE.md")
    memory_vault.ensure_vault_structure()

    monkeypatch.setattr("app.storage.runtime_settings.DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("app.storage.runtime_settings.RUNTIME_SETTINGS_FILE", str(tmp_path / "data" / "runtime_settings.json"))
    from app.storage.checklist_store import ChecklistStore
    lists = ChecklistStore(tmp_path / 'data' / 'checklists.sqlite3')
    monkeypatch.setattr('app.storage.checklist_store.checklist_store', lists)
    monkeypatch.setattr('app.agent.tools.checklist_tool.checklist_store', lists)
    monkeypatch.setattr('app.storage.sync_tombstones.TOMBSTONES_FILE', tmp_path / 'data' / 'sync_tombstones.json')
    monkeypatch.setattr("app.agent.action_executor.auto_approvals", AutoApprovalStore(str(tmp_path / "auto_approvals.json")))

    store = ActionStore(tmp_path / "journal.sqlite3")
    monkeypatch.setattr("app.storage.action_store.action_store", store)
    monkeypatch.setattr("app.agent.action_executor.action_store", store)
    monkeypatch.setattr("app.storage.task_store.TASKS_FILE", str(tmp_path / "tasks.json"))
    yield SimpleNamespace(store=store, root=tmp_path)
    if store._runtime_lock:
        store._runtime_lock.close()


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
