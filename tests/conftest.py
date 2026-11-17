import sys
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path so tests can import the `app` package
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _import_vault_outside_project_data() -> None:
    """``app.services.memory_vault`` cria data/vault/ (com o perfil modelo) ao ser importado.

    O módulo é importado com o cwd num diretório temporário e os caminhos ficam fixos lá,
    para nenhum teste criar nem alterar o cofre em data/ do projeto. ``isolated_lote6_data``
    continua trocando os caminhos por teste.
    """
    import atexit
    import importlib
    import os
    import shutil
    import tempfile

    import app.services  # noqa: F401  (o pacote importa com o cwd real)

    root = Path(tempfile.mkdtemp(prefix="jarvis-tests-vault-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    cwd = os.getcwd()
    os.chdir(root)
    try:
        vault = importlib.import_module("app.services.memory_vault")
    finally:
        os.chdir(cwd)
    base = root / "data" / "vault"
    vault.VAULT_DIR = base
    vault.DAILY_NOTES_DIR = base / "01-Daily-Notes"
    vault.PROFILE_DIR = base / "02-User-Profile"
    vault.PRIMING_DIR = base / "03-Priming-Notes"
    vault.PROJECTS_DIR = base / "04-Projects"
    vault.PROFILE_FILE = vault.PROFILE_DIR / "USER-PROFILE.md"


_import_vault_outside_project_data()


@pytest.fixture(autouse=True)
def isolated_credentials(monkeypatch, tmp_path):
    """Nenhum teste acessa o cofre de credenciais real do Windows."""
    from app.storage import credential_store
    from app.storage import runtime_settings
    monkeypatch.setattr(runtime_settings, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(runtime_settings, "RUNTIME_SETTINGS_FILE", str(tmp_path / "runtime_settings.json"))
    values = {}
    monkeypatch.setattr(credential_store, "save_key", lambda name, value: values.__setitem__(name, value))
    monkeypatch.setattr(credential_store, "load_key", lambda name: values.get(name))
    monkeypatch.setattr(credential_store, "delete_key", lambda name: values.pop(name, None))
    return values


@pytest.fixture(autouse=True)
def isolated_sessions(monkeypatch, tmp_path):
    monkeypatch.setattr("app.storage.session_store.SESSIONS_FILE", str(tmp_path / "sessions.json"))


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


@pytest.fixture(autouse=True)
def isolated_identity(tmp_path, monkeypatch):
    """Never use real biometrics or grant tests access to the owner's profile."""
    from app.services import identity
    monkeypatch.setattr(identity, 'IDENTITY_FILE', tmp_path / 'identity_profiles.json')
    monkeypatch.setattr(identity, 'FACE_DIR', tmp_path)
    monkeypatch.setattr(identity, '_password_failures', 0)
    monkeypatch.setattr(identity, '_password_retry_at', 0.0)


@pytest.fixture(autouse=True)
def isolated_app_lock(tmp_path, monkeypatch):
    """Test requests never depend on or change the owner's actual app lock."""
    from app.services.app_lock import app_lock
    monkeypatch.setattr(app_lock, 'path', tmp_path / 'app_lock.json')
    monkeypatch.setattr(app_lock, 'sessions', {})
    monkeypatch.setattr(app_lock, 'failures', 0)
    monkeypatch.setattr(app_lock, 'retry_at', 0.0)
