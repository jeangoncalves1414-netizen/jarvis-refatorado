"""Aprovações automáticas (lote 7, pacote 1): regras com escopo, alvo vazio, script com descrição repetida,
expiração, revogação e Modo liberado com e sem validade. Tudo em tmp: nada toca data/auto_approvals.json."""
import json
import time

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.storage.action_store import ActionStore
from app.storage.auto_approvals import AutoApprovalStore, _end_of_day
from app.ui.panel.api.approvals import handle_approvals_get, handle_approvals_post


@pytest.fixture
def approvals(isolated_auto_approvals):
    return isolated_auto_approvals


@pytest.fixture
def executor(tmp_path, approvals):
    store = ActionStore(tmp_path / "journal.sqlite3")
    return ActionExecutor(None, ToolCallGuardrailController(), lambda name, args, text: ToolResult(True, "ok"),
                          metadata_for=TOOL_CATALOG.get, store=store)


def post(path, **payload):
    return handle_approvals_post(path, json.dumps(payload).encode(), None)


def allow_from_proposal(action_id, **extra):
    return post("/api/approvals/rules", action_id=action_id, **extra)


REAL_TIME = time.time


def clock(monkeypatch, offset):
    monkeypatch.setattr(time, "time", lambda: REAL_TIME() + offset)


SCRIPT = {"description": "limpar a pasta temporária", "code": "print('inofensivo')"}
OTHER_CODE = {"description": "limpar a pasta temporária", "code": "import os; os.system('echo outro código')"}


# ── regras com escopo ───────────────────────────────────────────────────────
def test_rule_matches_tool_operation_and_target(approvals):
    rule = approvals.add_rule("open_windows_app", "close", "Spotify.exe", "always")
    assert approvals.match("open_windows_app", "close", "spotify.exe")["id"] == rule["id"]
    assert approvals.match("open_windows_app", "open", "Spotify.exe") is None
    assert approvals.match("open_windows_app", "close", "Chrome.exe") is None
    assert approvals.match("outra_ferramenta", "close", "Spotify.exe") is None
    assert approvals.list_rules()[0]["uses"] == 1


def test_low_risk_rule_with_empty_operation_and_target_is_a_wildcard(approvals):
    approvals.add_rule("habit_tool", "", "", "always")
    assert approvals.match("habit_tool", "create", "Ler", risk="low") is not None
    assert approvals.match("habit_tool", "", "", risk="low") is not None


def test_new_rule_defaults_to_now_not_always(approvals, executor):
    action = executor.propose("phantom_typer", {"text": "olá"})
    status, body = allow_from_proposal(action.id)
    assert status == 200 and body["rule"]["duration"] == "now"
    assert body["rule"]["expires_at"] is not None


# ── alvo vazio ──────────────────────────────────────────────────────────────
def test_high_risk_rule_without_target_needs_extra_confirmation(approvals):
    with pytest.raises(ValueError, match="risco alto"):
        approvals.add_rule("phantom_typer", "", "", "always", risk="high")
    assert approvals.list_rules() == []
    rule = approvals.add_rule("phantom_typer", "", "", "now", risk="high", broad=True)
    assert rule["broad"] is True
    assert approvals.match("phantom_typer", "", "", risk="high") is not None


def test_manual_rule_for_high_tool_without_target_is_refused_until_confirmed(approvals):
    status, body = post("/api/approvals/rules", tool="phantom_typer", duration="now")
    assert status == 400 and "qualquer alvo" in body["error"]
    assert approvals.list_rules() == []
    status, body = post("/api/approvals/rules", tool="phantom_typer", duration="now", confirm_broad=True)
    assert status == 200 and body["rule"]["broad"] is True


def test_rule_from_phantom_typer_proposal_is_bound_to_the_exact_text(approvals, executor):
    first = executor.propose("phantom_typer", {"text": "bom dia"})
    assert first.status == "awaiting_confirmation"
    status, body = allow_from_proposal(first.id, duration="today")
    assert status == 200 and body["rule"]["digest"] and "argumentos exatos" in body["rule"]["label"]
    assert executor.propose("phantom_typer", {"text": "bom dia"}).status == "authorized"
    assert executor.propose("phantom_typer", {"text": "apague tudo"}).status == "awaiting_confirmation"


def test_legacy_high_rule_without_target_no_longer_matches(approvals):
    approvals._write({"rules": [{"id": "apr_old", "tool": "phantom_typer", "operation": "", "target": "", "label": "phantom_typer",
                                 "duration": "always", "expires_at": None, "uses": 0, "revoked": False}]})
    assert approvals.match("phantom_typer", "", "", risk="high", digest="x") is None


# ── script_runner: descrição repetida com código diferente ──────────────────
def test_script_rule_does_not_cover_other_code_with_the_same_description(approvals, executor):
    first = executor.propose("script_runner", SCRIPT)
    assert first.risk == "critical" and first.status == "awaiting_confirmation"
    status, body = allow_from_proposal(first.id, duration="always")
    assert status == 200 and body["rule"]["digest"] == first.arguments_digest
    assert executor.propose("script_runner", SCRIPT).status == "authorized"  # mesmos argumentos
    swapped = executor.propose("script_runner", OTHER_CODE)
    assert swapped.status == "awaiting_confirmation"
    assert [rule["uses"] for rule in approvals.list_rules()] == [1]


def test_manual_rule_for_critical_tool_is_refused(approvals):
    status, body = post("/api/approvals/rules", tool="script_runner", target="limpar a pasta temporária", duration="always", confirm_broad=True)
    assert status == 400 and "críticas" in body["error"]
    assert approvals.list_rules() == []
    with pytest.raises(ValueError):
        approvals.add_rule("script_runner", "", "x", "always", risk="critical")


def test_critical_rule_without_digest_never_matches(approvals):
    approvals._write({"rules": [{"id": "apr_old", "tool": "script_runner", "operation": "", "target": "limpar", "label": "x",
                                 "duration": "always", "expires_at": None, "uses": 0, "revoked": False}]})
    assert approvals.match("script_runner", "", "limpar", risk="critical", digest="abc") is None


def test_rule_with_target_still_applies_to_high_risk_calls(approvals, executor):
    first = executor.propose("browser_agent", {"goal": "abrir o site do banco"})
    assert first.risk == "high"
    status, body = allow_from_proposal(first.id)
    assert status == 200 and not body["rule"]["digest"]
    assert executor.propose("browser_agent", {"goal": "abrir o site do banco", "extra": 1}).status == "authorized"
    assert executor.propose("browser_agent", {"goal": "outro objetivo"}).status == "awaiting_confirmation"


def test_unknown_proposal_cannot_become_a_rule(approvals):
    status, body = allow_from_proposal("act_inexistente")
    assert status == 404 and approvals.list_rules() == []


# ── expiração e revogação ───────────────────────────────────────────────────
def test_rule_expires_after_its_duration(approvals, monkeypatch):
    approvals.add_rule("habit_tool", "create", "Ler", "now")
    assert approvals.match("habit_tool", "create", "Ler") is not None
    clock(monkeypatch, 11 * 60)
    assert approvals.match("habit_tool", "create", "Ler") is None
    assert approvals.list_rules() == []
    assert approvals.list_rules(include_inactive=True)[0]["active"] is False


def test_rule_without_expiry_survives_long_periods(approvals, monkeypatch):
    approvals.add_rule("habit_tool", "create", "Ler", "always")
    clock(monkeypatch, 400 * 86400)
    assert approvals.match("habit_tool", "create", "Ler") is not None


def test_revoked_rule_stops_matching(approvals):
    rule = approvals.add_rule("habit_tool", "create", "Ler", "always")
    status, body = post(f"/api/approvals/rules/{rule['id']}", revoke=True)
    assert status == 200 and body["rules"] == []
    assert approvals.match("habit_tool", "create", "Ler") is None
    assert post("/api/approvals/rules/apr_nao_existe", revoke=True)[0] == 404


def test_update_duration_changes_expiry(approvals):
    rule = approvals.add_rule("habit_tool", "", "", "now")
    status, body = post(f"/api/approvals/rules/{rule['id']}", duration="always")
    assert status == 200 and body["rules"][0]["expires_at"] is None


# ── Modo liberado ───────────────────────────────────────────────────────────
def test_liberated_mode_without_validity_keeps_current_behavior(approvals, executor, monkeypatch):
    status, body = post("/api/approvals/mode", enabled=True)
    assert status == 200 and body["mode"] == {"enabled": True, "persist": False, "until": None}
    action = executor.propose("script_runner", SCRIPT)
    assert action.status == "authorized" and "modo liberado" in action.result_summary
    clock(monkeypatch, 90 * 86400)
    assert approvals.liberated() is True
    assert executor.propose("phantom_typer", {"text": "x"}).status == "authorized"


def test_liberated_mode_with_one_hour_validity_turns_itself_off(approvals, executor, monkeypatch):
    status, body = post("/api/approvals/mode", enabled=True, validity="1h")
    assert status == 200 and body["mode"]["until"] is not None
    assert 3500 < body["mode"]["until"] - time.time() <= 3600
    assert executor.propose("script_runner", SCRIPT).status == "authorized"
    clock(monkeypatch, 59 * 60)
    assert approvals.liberated() is True
    clock(monkeypatch, 61 * 60)
    assert approvals.liberated() is False
    assert approvals.mode() == {"enabled": False, "persist": False, "until": None}
    assert executor.propose("script_runner", SCRIPT).status == "awaiting_confirmation"
    assert handle_approvals_get(["api", "approvals"], None)[1]["mode"]["enabled"] is False


def test_liberated_mode_today_ends_at_midnight(approvals):
    mode = approvals.set_mode(True, validity="today")
    assert mode["enabled"] is True and mode["until"] == _end_of_day(time.time())


def test_changing_persist_keeps_the_chosen_validity(approvals):
    until = approvals.set_mode(True, validity="1h")["until"]
    mode = approvals.set_mode(True, persist=True)
    assert mode == {"enabled": True, "persist": True, "until": until}
    assert approvals.set_mode(False)["until"] is None


def test_invalid_validity_is_rejected(approvals):
    status, body = post("/api/approvals/mode", enabled=True, validity="semana")
    assert status == 400 and approvals.mode()["enabled"] is False


def test_persisted_liberated_mode_respects_validity_after_restart(tmp_path):
    path = str(tmp_path / "persist.json")
    first = AutoApprovalStore(path)
    first.set_mode(True, persist=True, validity="1h")
    assert AutoApprovalStore(path).liberated() is True
    first.set_mode(True, persist=True)
    data = json.loads(open(path, encoding="utf-8").read())
    data["liberated_until"] = time.time() - 5
    open(path, "w", encoding="utf-8").write(json.dumps(data))
    assert AutoApprovalStore(path).liberated() is False
    plain = AutoApprovalStore(str(tmp_path / "plain.json"))
    plain.set_mode(True)  # sem persist: o backend sempre volta desligado
    assert AutoApprovalStore(str(tmp_path / "plain.json")).liberated() is False


def test_autouse_fixture_keeps_the_real_store_untouched(approvals, tmp_path):
    from app.agent import action_executor
    from app.storage import auto_approvals as module
    assert action_executor.auto_approvals is approvals and module.auto_approvals is approvals
    assert approvals.path.startswith(str(tmp_path))


def test_categories_separate_commands_single_and_bulk_deletes(approvals, executor):
    status, data = post("/api/approvals/mode", enabled=True, persist=True, categories={"commands": False, "bulk": False})
    assert status == 200 and data["categories"]["remove"]
    assert executor.propose("script_runner", SCRIPT).status == "awaiting_confirmation"
    assert executor.propose("habit_tool", {"action": "delete", "habit_id": "a"}).status == "authorized"
    assert executor.propose("personal_records", {"action": "delete_many", "record_ids": ["a", "b"]}).status == "awaiting_confirmation"
    assert not AutoApprovalStore(approvals.path).allows("bulk")
    assert post("/api/approvals/mode", enabled=True, categories={"unknown": True})[0] == 400
