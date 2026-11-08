"""Sincronização total com a nuvem: mesclagem campo a campo e snapshot do backend.

Todas as chaves aqui são falsas e nenhum teste usa rede ou os dados reais.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.storage import backend_sync as bs
from app.storage import runtime_settings as rs

FAKE_GROQ = "gsk_FAKE_groq_0000000000000000AAAA"
FAKE_GEMINI = "AIzaFAKE_gemini_11111111111111BBBB"
FAKE_FISH = "fish_FAKE_22222222222222222222CCCC"
FAKE_KEYS = (FAKE_GROQ, FAKE_GEMINI, FAKE_FISH)


def field(value, ts):
    return {"v": value, "ts": ts}


@pytest.fixture
def use_device(monkeypatch, tmp_path):
    """Troca o armazenamento local para um 'dispositivo' isolado em diretório temporário."""
    monkeypatch.setattr(os, "environ", os.environ.copy())

    def switch(name: str) -> Path:
        root = tmp_path / name
        (root / "data").mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(rs, "DATA_DIR", str(root / "data"))
        monkeypatch.setattr(rs, "RUNTIME_SETTINGS_FILE", str(root / "data" / "runtime_settings.json"))
        monkeypatch.setattr("app.storage.task_store.TASKS_FILE", str(root / "data" / "tasks.json"))
        from app.storage.goal_store import GoalStore

        monkeypatch.setattr("app.storage.goal_store.goal_store", GoalStore(root / "data" / "goals.json"))
        monkeypatch.setattr(bs, "MEMORY_FILE", root / "data" / "memory.json")
        monkeypatch.setattr("app.storage.user_preferences.preference_store.file_path", str(root / "data" / "preferences.json"))
        monkeypatch.setattr("app.services.memory_vault.VAULT_DIR", root / "data" / "vault")
        monkeypatch.setattr("app.services.habits.DB_PATH", root / "data" / "lifestyle.db")
        monkeypatch.setattr("app.storage.sync_tombstones.TOMBSTONES_FILE", root / "data" / "sync_tombstones.json")
        (root / "data" / "vault").mkdir(exist_ok=True)
        from app.services import finance, habits, tasks

        habits.init_db()
        tasks.init_task_tables()
        finance.init_finance_tables()
        return root

    return switch


# ---------------------------------------------------------------------------
# Mesclagem pura de configurações
# ---------------------------------------------------------------------------
def test_merge_preserves_keys_from_two_devices_with_different_providers():
    pc = {"api_keys.groq": field(FAKE_GROQ, 100), "llm_provider": field("groq", 100)}
    phone = {"api_keys.gemini": field(FAKE_GEMINI, 200), "api_keys.fish": field(FAKE_FISH, 150)}

    merged = bs.merge_settings_fields(pc, phone)

    assert merged["api_keys.groq"]["v"] == FAKE_GROQ
    assert merged["api_keys.gemini"]["v"] == FAKE_GEMINI
    assert merged["api_keys.fish"]["v"] == FAKE_FISH
    assert merged["llm_provider"]["v"] == "groq"
    # A ordem dos argumentos não muda o resultado.
    assert bs.merge_settings_fields(phone, pc) == merged


def test_merge_empty_never_overwrites_filled_even_when_newer():
    local = {"api_keys.groq": field(FAKE_GROQ, 100), "agent_profile.style": field("Direto", 100)}
    remote = {"api_keys.groq": field("", 999), "agent_profile.style": field("   ".strip(), 999)}

    merged = bs.merge_settings_fields(local, remote)

    assert merged["api_keys.groq"] == field(FAKE_GROQ, 100)
    assert merged["agent_profile.style"] == field("Direto", 100)
    assert bs.merge_settings_fields(remote, local) == merged


def test_merge_same_field_newest_stamp_wins_and_tie_keeps_local():
    older = {"api_keys.fish": field("fish_FAKE_old_AAAA", 10)}
    newer = {"api_keys.fish": field("fish_FAKE_new_BBBB", 20)}

    assert bs.merge_settings_fields(older, newer)["api_keys.fish"]["v"] == "fish_FAKE_new_BBBB"
    assert bs.merge_settings_fields(newer, older)["api_keys.fish"]["v"] == "fish_FAKE_new_BBBB"
    tie = bs.merge_settings_fields({"x.a": field("local", 5)}, {"x.a": field("remote", 5)})
    assert tie["x.a"]["v"] == "local"


def test_merge_ignores_malformed_remote_entries():
    merged = bs.merge_settings_fields({"llm_provider": field("groq", 1)}, {"llm_provider": "lixo", "../etc": field("x", 1), "api_keys.groq": {"ts": 1}})
    assert merged == {"llm_provider": field("groq", 1)}


# ---------------------------------------------------------------------------
# Carimbos por campo no armazenamento local
# ---------------------------------------------------------------------------
def test_runtime_settings_stamps_only_changed_fields(use_device):
    use_device("pc")
    rs.set_api_keys({"groq": FAKE_GROQ})
    first = bs.collect_settings_fields()["api_keys.groq"]["ts"]
    assert first > 0

    rs.set_api_keys({"groq": FAKE_GROQ, "gemini": FAKE_GEMINI})
    fields = bs.collect_settings_fields()
    assert fields["api_keys.groq"]["ts"] == first
    assert fields["api_keys.gemini"]["v"] == FAKE_GEMINI
    assert fields["api_keys.gemini"]["ts"] >= first


# ---------------------------------------------------------------------------
# Snapshot completo: entra e volta na restauração
# ---------------------------------------------------------------------------
def populate_pc(use_device):
    root = use_device("pc")
    rs.set_api_keys({"groq": FAKE_GROQ, "gemini": FAKE_GEMINI, "fish": FAKE_FISH})
    rs.set_llm_provider("groq")
    rs.set_agent_profile({"name": "Atena", "style": "Calma e objetiva.", "wake_phrase": "ei atena"})

    from app.storage import task_store
    from app.storage.goal_store import GoalStore
    import app.storage.goal_store as goal_module

    task = task_store.add_task("Pagar a conta de luz")
    goal = goal_module.goal_store.create("Estudar 1h por dia", "Abrir o caderno")
    (root / "data" / "memory.json").write_text(json.dumps({"preferences": [{"key": "estilo", "value": "curto"}], "facts": ["Gosta de café"], "sessions": []}), encoding="utf-8")
    (root / "data" / "preferences.json").write_text(json.dumps({"preferences": ["Responder sem emoji"]}), encoding="utf-8")
    note = root / "data" / "vault" / "04-Projects" / "ideia.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Ideia\nMeu plano.", encoding="utf-8")

    from app.services.finance import FinanceService
    from app.services.habits import HabitService
    from app.services.tasks import TaskService

    HabitService.create_habit("hab_1", "Beber água")
    TaskService.create_task("rot_1", "Revisar contratos", subtasks=["Ler cláusula 3"])
    FinanceService.add_transaction("fin_1", "expense", 42.5, "Mercado", "Compras", "2026-11-01")
    return {"task": task, "goal": goal, "root": root}


def test_snapshot_round_trip_restores_everything_on_another_device(use_device):
    populate_pc(use_device)
    snapshot = json.loads(json.dumps(bs.collect_snapshot()))  # simula ida e volta pela nuvem

    use_device("phone")
    merged, summary = bs.sync_with_remote(snapshot)

    keys = rs.get_api_keys()
    assert keys["groq"] == FAKE_GROQ and keys["gemini"] == FAKE_GEMINI and keys["fish"] == FAKE_FISH
    assert rs.get_llm_provider() == "groq"
    assert os.environ["GROQ_API_KEY"] == FAKE_GROQ
    profile = rs.get_agent_profile()
    assert profile["name"] == "Atena" and profile["style"] == "Calma e objetiva." and profile["wake_phrase"] == "ei atena"

    from app.storage import task_store
    import app.storage.goal_store as goal_module

    assert [t["title"] for t in task_store.list_tasks()] == ["Pagar a conta de luz"]
    assert [g["title"] for g in goal_module.goal_store.list()] == ["Estudar 1h por dia"]
    memory = json.loads(bs.MEMORY_FILE.read_text(encoding="utf-8"))
    assert memory["facts"] == ["Gosta de café"] and memory["preferences"] == [{"key": "estilo", "value": "curto"}]
    assert bs._preferences_store().get_preferences() == ["Responder sem emoji"]
    vault = Path(rs.DATA_DIR) / "vault" / "04-Projects" / "ideia.md"
    assert vault.read_text(encoding="utf-8") == "# Ideia\nMeu plano."

    from app.services.finance import FinanceService
    from app.services.habits import HabitService
    from app.services.tasks import TaskService

    assert [t["id"] for t in FinanceService.list_transactions()] == ["fin_1"]
    assert [h["id"] for h in HabitService.list_habits()] == ["hab_1"]
    assert [t["id"] for t in TaskService.list_tasks(completed=None)] == ["rot_1"]
    assert summary["settings"] > 0 and summary["tasks"] == 1


def test_sync_between_two_devices_keeps_data_from_both(use_device):
    populate_pc(use_device)
    from app.storage import task_store

    pc_snapshot = json.loads(json.dumps(bs.collect_snapshot()))

    use_device("phone")
    rs.set_api_keys({"openrouter": "or_FAKE_33333333333333DDDD", "groq": ""})
    phone_task = task_store.add_task("Comprar pão")

    merged, _ = bs.sync_with_remote(pc_snapshot)

    keys = rs.get_api_keys()
    assert keys["openrouter"] == "or_FAKE_33333333333333DDDD"  # só o celular conhecia
    assert keys["groq"] == FAKE_GROQ  # vazio do celular não apaga o preenchido do PC
    titles = sorted(t["title"] for t in task_store.list_tasks())
    assert titles == ["Comprar pão", "Pagar a conta de luz"]
    assert phone_task["id"] in merged["tasks"]


def test_older_remote_does_not_overwrite_newer_local_rows_and_notes(use_device):
    root = populate_pc(use_device)["root"]
    old_snapshot = json.loads(json.dumps(bs.collect_snapshot()))
    # A edição local acontece depois do snapshot remoto.
    from app.services.finance import FinanceService

    FinanceService.add_transaction("fin_1", "expense", 99.0, "Mercado", "Compras (editado)", "2026-11-01")
    note = root / "data" / "vault" / "04-Projects" / "ideia.md"
    note.write_text("# Ideia\nVersão nova.", encoding="utf-8")
    os.utime(note, (old_snapshot["notes"]["04-Projects/ideia.md"]["mtime"] + 100,) * 2)

    bs.sync_with_remote(old_snapshot)

    assert FinanceService.list_transactions()[0]["amount"] == 99.0
    assert note.read_text(encoding="utf-8") == "# Ideia\nVersão nova."


def test_newer_remote_note_replaces_local_and_keeps_conflict_copy(use_device):
    root = populate_pc(use_device)["root"]
    note = root / "data" / "vault" / "04-Projects" / "ideia.md"
    remote = {"notes": {"04-Projects/ideia.md": {"content": "# Ideia\nVinda do celular.", "mtime": note.stat().st_mtime + 500}}}

    bs.sync_with_remote(remote)

    assert note.read_text(encoding="utf-8") == "# Ideia\nVinda do celular."
    saved = list((root / "data" / "vault" / ".conflitos").glob("ideia.*.md"))
    assert len(saved) == 1 and saved[0].read_text(encoding="utf-8") == "# Ideia\nMeu plano."


def test_remote_note_cannot_escape_the_vault(use_device):
    root = use_device("pc")
    remote = {"notes": {"../fora.md": {"content": "x", "mtime": 1}, "04-Projects/ok.md": {"content": "ok", "mtime": 1}}}

    bs.sync_with_remote(remote)

    assert not (root / "data" / "fora.md").exists()
    assert (root / "data" / "vault" / "04-Projects" / "ok.md").read_text(encoding="utf-8") == "ok"


def test_invalid_remote_providers_are_ignored(use_device):
    use_device("pc")
    rs.set_llm_provider("gemini")
    bs.sync_with_remote({"settings": {"llm_provider": field("inexistente", 9999999999999), "api_keys.desconhecido": field("x", 1)}})
    assert rs.get_llm_provider() == "gemini"
    assert "desconhecido" not in rs._read().get("api_keys", {})


# ---------------------------------------------------------------------------
# Lápides de exclusão (S1) e data de edição dos hábitos (S2)
# ---------------------------------------------------------------------------
def via_cloud(snapshot):
    return json.loads(json.dumps(snapshot))


def lifestyle_ids(table, column="id"):
    return sorted(row[column] for row in bs._collect_lifestyle()[table])


def test_deleting_on_one_device_does_not_come_back_after_merging_with_the_other(use_device):
    from app.services.finance import FinanceService
    from app.services.habits import HabitService
    from app.services.tasks import TaskService
    from app.storage import task_store

    populated = populate_pc(use_device)
    HabitService.check_in("hab_1", "2026-11-01")
    first = via_cloud(bs.collect_snapshot())
    use_device("phone")
    bs.sync_with_remote(first)
    phone_snapshot = via_cloud(bs.collect_snapshot())  # o celular ainda tem tudo

    pc = use_device("pc")
    FinanceService.delete_transaction("fin_1")
    HabitService.delete_habit("hab_1")
    TaskService.delete_task("rot_1")
    task_store.delete_task(populated["task"]["id"])
    (pc / "data" / "vault" / "04-Projects" / "ideia.md").unlink()  # apagada direto na pasta do cofre

    merged, summary = bs.sync_with_remote(phone_snapshot)

    assert FinanceService.list_transactions() == [] and HabitService.list_habits() == []
    assert TaskService.list_tasks(completed=None) == [] and task_store.list_tasks() == []
    assert lifestyle_ids("habit_logs", "habit_id") == [] and lifestyle_ids("task_subtasks", "task_id") == []
    assert not (pc / "data" / "vault" / "04-Projects" / "ideia.md").exists()
    assert set(merged["tombstones"]) >= {"tasks", "notes", "lifestyle.habits", "lifestyle.tasks", "lifestyle.finance_transactions"}
    assert summary["tombstones"] >= 5

    # A exclusão chega ao outro dispositivo pela nuvem.
    phone = use_device("phone")
    _, phone_summary = bs.sync_with_remote(via_cloud(merged))

    assert FinanceService.list_transactions() == [] and HabitService.list_habits() == []
    assert TaskService.list_tasks(completed=None) == [] and task_store.list_tasks() == []
    assert lifestyle_ids("habit_logs", "habit_id") == [] and lifestyle_ids("task_subtasks", "task_id") == []
    assert not (phone / "data" / "vault" / "04-Projects" / "ideia.md").exists()
    backup = list((phone / "data" / "vault" / ".conflitos").glob("ideia.apagada.*.md"))
    assert len(backup) == 1 and backup[0].read_text(encoding="utf-8") == "# Ideia\nMeu plano."
    assert phone_summary["lifestyle_rows_deleted"] >= 3 and phone_summary["notes_deleted"] == 1

    # E não volta numa sincronização seguinte com o snapshot velho do celular.
    use_device("pc")
    bs.sync_with_remote(phone_snapshot)
    assert FinanceService.list_transactions() == [] and task_store.list_tasks() == []


def test_edit_or_recreation_after_the_deletion_wins_over_the_tombstone():
    now = time.time()
    tombstones = {"lifestyle.finance_transactions": {'["fin_1"]': now - 10}, "tasks": {"t1": now - 10}}
    old_row = {"id": "fin_1", "type": "expense", "amount": 1.0, "timestamp": now - 20}
    new_row = {**old_row, "amount": 2.0, "timestamp": now}

    dropped = bs.merge_snapshots({"tombstones": tombstones}, {"lifestyle": {"finance_transactions": [old_row]}, "tasks": {"t1": {"id": "t1", "updated_at": now - 20}}})
    kept = bs.merge_snapshots({"tombstones": tombstones}, {"lifestyle": {"finance_transactions": [new_row]}, "tasks": {"t1": {"id": "t1", "updated_at": now}}})

    assert dropped["lifestyle"]["finance_transactions"] == [] and dropped["tasks"] == {}
    assert kept["lifestyle"]["finance_transactions"] == [new_row] and "t1" in kept["tasks"]


def test_habit_edit_on_one_device_reaches_the_other(use_device):
    from app.services.habits import HabitService

    populate_pc(use_device)
    first = via_cloud(bs.collect_snapshot())
    use_device("phone")
    bs.sync_with_remote(first)
    stale_phone = via_cloud(bs.collect_snapshot())

    use_device("pc")
    time.sleep(0.01)
    HabitService.update_habit("hab_1", name="Beber 2 litros de água")
    bs.sync_with_remote(stale_phone)  # o snapshot velho do celular não desfaz a edição
    assert HabitService.get_habit("hab_1")["name"] == "Beber 2 litros de água"
    pc_snapshot = via_cloud(bs.collect_snapshot())

    use_device("phone")
    bs.sync_with_remote(pc_snapshot)
    habit = HabitService.get_habit("hab_1")
    assert habit["name"] == "Beber 2 litros de água"
    assert habit["updated_at"] > habit["created_at"]


def test_old_snapshot_without_tombstones_or_habit_dates_still_works(use_device):
    from app.services.finance import FinanceService
    from app.services.habits import HabitService

    populate_pc(use_device)
    old = via_cloud(bs.collect_snapshot())
    old.pop("tombstones")
    for row in old["lifestyle"]["habits"]:
        row.pop("updated_at")

    use_device("phone")
    merged, _ = bs.sync_with_remote(old)

    assert [h["id"] for h in HabitService.list_habits()] == ["hab_1"]
    assert [t["id"] for t in FinanceService.list_transactions()] == ["fin_1"]
    assert merged["tombstones"] == {}
    # Sem data de edição, o hábito local não é trocado pelo remoto (empate: local).
    assert bs.merge_lifestyle({"habits": [{"id": "h", "name": "local", "created_at": 5}]}, {"habits": [{"id": "h", "name": "remoto", "created_at": 5}]})["habits"][0]["name"] == "local"


def test_tombstones_are_validated_and_old_ones_are_pruned():
    from app.storage import sync_tombstones as tomb

    now = time.time()
    raw = {
        "tasks": {"velha": now - tomb.RETENTION_SECONDS - 60, "nova": now - 60, "futura": now + 9999, "ruim": "x"},
        "desconhecido": {"a": now},
        "notes": {"x" * (tomb.MAX_KEY_LENGTH + 1): now},
    }
    cleaned = tomb.clean(raw, now)

    assert cleaned == {"tasks": {"nova": now - 60, "futura": now}}
    assert tomb.merge({"tasks": {"a": now - 50}}, {"tasks": {"a": now - 10}}, now) == {"tasks": {"a": now - 10}}
    tomb.record("tasks", "t1", now - 5)
    tomb.store({"tasks": {"t1": now - tomb.RETENTION_SECONDS - 1}})
    assert tomb.load()["tasks"]["t1"] == now - 5


# ---------------------------------------------------------------------------
# API e logs
# ---------------------------------------------------------------------------
def test_sync_endpoints_round_trip_without_printing_secrets(use_device, capsys, caplog):
    from app.ui.panel.api.settings import handle_settings_get, handle_settings_post

    populate_pc(use_device)
    handler = SimpleNamespace(settings=Settings())
    caplog.set_level("DEBUG")

    status, body = handle_settings_get(["", "settings", "sync-snapshot"], handler)
    assert status == 200 and body["snapshot"]["settings"]["api_keys.groq"]["v"] == FAKE_GROQ

    use_device("phone")
    payload = json.dumps({"snapshot": body["snapshot"]}).encode("utf-8")
    status, result = handle_settings_post("/api/settings/sync-merge", payload, handler)

    assert status == 200 and result["ok"] is True
    assert rs.get_api_keys()["groq"] == FAKE_GROQ
    assert handler.settings.groq_api_key == FAKE_GROQ  # objeto Settings em memória atualizado
    assert result["snapshot"]["settings"]["api_keys.gemini"]["v"] == FAKE_GEMINI
    # O resumo só traz contagens, nunca valores.
    assert not any(key in json.dumps(result["summary"]) for key in FAKE_KEYS)
    out = capsys.readouterr()
    logged = out.out + out.err + caplog.text
    assert not any(key in logged for key in FAKE_KEYS)


def test_sync_endpoint_rejects_bad_payloads(use_device):
    from app.ui.panel.api.settings import handle_settings_post

    use_device("pc")
    handler = SimpleNamespace(settings=Settings())
    assert handle_settings_post("/api/settings/sync-merge", b"{nao e json", handler)[0] == 400
    assert handle_settings_post("/api/settings/sync-merge", json.dumps({"snapshot": [1]}).encode(), handler)[0] == 400


def test_frontend_cloud_code_never_logs_full_keys_or_urls():
    """Garante estaticamente que o cliente não imprime snapshot, linhas da nuvem nem URLs."""
    source = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "utils" / "jarvisCloud.ts").read_text(encoding="utf-8")
    for forbidden in ("Request URL", "Supabase URL", "Response rows", "Push response", "Applying vault locally:", "Raw habits", "Vault pulled from cloud:"):
        assert forbidden not in source
    for line in source.splitlines():
        if "console." in line:
            assert "vault.keys" not in line and "keys," not in line and "rows" not in line


# ---------------------------------------------------------------------------
# Mesclagem do cliente (TypeScript puro), executada com o Node, se existir
# ---------------------------------------------------------------------------
@pytest.mark.skipif(shutil.which("node") is None, reason="Node não está disponível")
def test_frontend_merge_helpers_keep_fields_from_both_devices():
    module = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "utils" / "syncMerge.ts").as_uri()
    script = f"""
import * as m from '{module}'
const a = {{ 'api_keys.groq': {{ v: '{FAKE_GROQ}', ts: 100 }}, 'llm_provider': {{ v: 'groq', ts: 100 }} }}
const b = {{ 'api_keys.gemini': {{ v: '{FAKE_GEMINI}', ts: 200 }}, 'api_keys.groq': {{ v: '', ts: 900 }}, 'llm_provider': {{ v: 'gemini', ts: 300 }} }}
const fields = m.mergeStampedFields(a, b)
const section = m.mergeSection({{ d1: {{ agua: 1 }}, lista: [{{ id: 'a', n: 1 }}] }}, {{ d1: {{ agua: 3, cafe: 2 }}, lista: [{{ id: 'b', n: 2 }}] }}, 10, 20)
console.log(JSON.stringify({{
  fields,
  section,
  keepsFilled: m.mergeSection('abc', '', 99, 1),
  masked: m.maskKeyList('{FAKE_GROQ},{FAKE_GEMINI}'),
  redacted: m.redactForLog({{ keys: {{ groq: '{FAKE_GROQ}' }}, authorization: 'Bearer abc', nome: 'ok' }}),
}}))
"""
    done = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, encoding="utf-8", timeout=60)
    assert done.returncode == 0, done.stderr[-500:]
    out = json.loads(done.stdout.strip().splitlines()[-1])
    assert out["fields"]["api_keys.groq"]["v"] == FAKE_GROQ
    assert out["fields"]["api_keys.gemini"]["v"] == FAKE_GEMINI
    assert out["fields"]["llm_provider"]["v"] == "gemini"
    assert out["section"]["d1"] == {"agua": 3, "cafe": 2}
    assert sorted(i["id"] for i in out["section"]["lista"]) == ["a", "b"]
    assert out["keepsFilled"] == "abc"
    assert out["masked"] == "•••• AAAA, •••• BBBB"
    assert FAKE_GROQ not in json.dumps(out["redacted"]) and out["redacted"]["nome"] == "ok"
