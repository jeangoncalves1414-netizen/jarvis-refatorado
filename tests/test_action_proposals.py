"""C1: propostas de aprovação com alvo, mudança, reversibilidade e escopo."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.core.action_proposals import build_proposal_preview
from app.core.actions import ToolMetadata
from app.services.app_manager import AppManager
from app.storage.action_store import ActionStore

LABELS = ("Alvo: ", "Mudança: ", "Reversibilidade: ", "Escopo: ")


@pytest.fixture(autouse=True)
def _fake_registry(monkeypatch):
    """O registro do Windows nunca é lido: um único app instalado fictício."""
    monkeypatch.setattr(AppManager, "_scan_registry", lambda self: {"foo studio": r"C:\Apps\Foo\foo.exe"})


def _executor(tmp_path, metadata_for=TOOL_CATALOG.get):
    calls = []
    executor = ActionExecutor(
        None, ToolCallGuardrailController(),
        lambda name, args, user: calls.append((name, args)) or ToolResult(True, "feito"),
        metadata_for=metadata_for, store=ActionStore(tmp_path / "actions.jsonl"), source="test",
    )
    return executor, calls


def _process(name: str):
    return SimpleNamespace(info={"pid": 1, "name": name}, terminate=MagicMock(), kill=MagicMock())


def _fields(preview: str) -> dict[str, str]:
    """Separa os quatro campos pelo rótulo; falha se algum faltar ou vier fora de ordem."""
    positions = [preview.index(label) for label in LABELS]
    assert positions == sorted(positions)
    bounds = positions + [len(preview)]
    return {label[:-2]: preview[bounds[i] + len(label): bounds[i + 1]].strip() for i, label in enumerate(LABELS)}


def test_every_catalog_tool_has_a_complete_declared_proposal():
    for name, metadata in TOOL_CATALOG.items():
        preview = build_proposal_preview(name, {}, metadata)
        fields = _fields(preview)
        assert "Parâmetros registrados" not in preview, name
        assert "não declarad" not in fields["Mudança"].lower(), name
        assert "não declarad" not in fields["Reversibilidade"].lower(), name
        assert "não declarad" not in fields["Escopo"].lower(), name
        assert len(preview) <= 800, name


def test_closing_app_lists_matching_processes_and_does_not_touch_them(tmp_path):
    executor, calls = _executor(tmp_path)
    procs = [_process("Spotify.exe"), _process("spotify.exe"), _process("Spotify.exe"), _process("Spotify2.exe"), _process("notepad.exe")]
    with patch("psutil.process_iter", side_effect=lambda *_a, **_k: iter(procs)):
        message = executor.execute("open_windows_app", {"action": "close", "app_name": "spotify"}, "feche o spotify")
    action = executor.last_action
    assert (action.risk, action.status) == ("high", "awaiting_confirmation")
    fields = _fields(action.preview)
    assert "spotify" in fields["Alvo"]
    assert "Spotify.exe (3 processos)" in fields["Alvo"]
    assert "Spotify2" not in fields["Alvo"] and "notepad" not in fields["Alvo"]
    assert "encerra" in fields["Mudança"].lower()
    assert fields["Reversibilidade"].startswith("Não reversível")
    assert "esta execução" in fields["Escopo"]
    assert action.preview in message and "exige confirmação" in message
    assert calls == []
    for proc in procs:
        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()


def test_closing_app_with_no_running_process_says_nothing_will_be_closed(tmp_path):
    executor, _calls = _executor(tmp_path)
    with patch("psutil.process_iter", side_effect=lambda *_a, **_k: iter([_process("notepad.exe")])):
        executor.execute("open_windows_app", {"action": "close", "app_name": "spotify"}, "feche o spotify")
    assert "nenhum processo em execução" in _fields(executor.last_action.preview)["Alvo"]


def test_failed_process_lookup_is_reported_not_raised(tmp_path):
    executor, _calls = _executor(tmp_path)
    with patch("psutil.process_iter", side_effect=OSError("sem acesso")):
        executor.execute("open_windows_app", {"action": "close", "app_name": "spotify"}, "feche o spotify")
    assert executor.last_action.status == "awaiting_confirmation"
    assert "não foi possível consultar" in executor.last_action.preview


def test_closing_many_executables_lists_a_few_and_counts_the_rest():
    names = [f"app{i}.exe" for i in range(8)]
    with patch("app.services.app_manager.running_processes_for", return_value=[(n, 1) for n in names]):
        preview = build_proposal_preview("open_windows_app", {"action": "close", "app_name": "app"}, TOOL_CATALOG["open_windows_app"])
    assert "app0.exe (1 processo)" in preview and "app4.exe" in preview
    assert "app5.exe" not in preview and "e mais 3 executável(is)" in preview


def test_opening_unknown_target_warns_in_the_proposal(tmp_path):
    executor, _calls = _executor(tmp_path)
    executor.execute("open_windows_app", {"action": "open", "app_name": "cmd /c echo x"}, "abra isso")
    fields = _fields(executor.last_action.preview)
    assert executor.last_action.status == "awaiting_confirmation"
    assert "cmd /c echo x" in fields["Alvo"] and "fora dos aplicativos conhecidos" in fields["Alvo"]


def test_unknown_tool_falls_back_to_honest_text_without_argument_values(tmp_path):
    executor, _calls = _executor(tmp_path, metadata_for=lambda _name: None)
    executor.execute("plugin_novo", {"query": "valor-secreto-123", "api_key": "chave-abc"}, "faça")
    action = executor.last_action
    fields = _fields(action.preview)
    assert action.status == "awaiting_confirmation"
    assert "Parâmetros registrados" not in action.preview
    assert "plugin novo" in fields["Alvo"] and "query, api_key" in fields["Alvo"]
    assert "não declarada" in fields["Mudança"].lower()
    assert "irreversível" in fields["Reversibilidade"]
    assert "valor-secreto-123" not in action.preview and "chave-abc" not in action.preview


def test_unrecognized_system_operation_is_named_and_does_not_list_processes(tmp_path):
    executor, _calls = _executor(tmp_path)
    with patch("psutil.process_iter") as process_iter:
        executor.execute("system_control", {"action": "kill_process", "app_name": "explorer"}, "mate o explorer")
    process_iter.assert_not_called()
    fields = _fields(executor.last_action.preview)
    assert executor.last_action.risk == "critical"
    assert "explorer" in fields["Alvo"] and "'kill_process' não reconhecida" in fields["Mudança"]


def test_system_control_brightness_and_lock_describe_effect_and_undo():
    metadata = TOOL_CATALOG["system_control"]
    brightness = _fields(build_proposal_preview("system_control", {"action": "set_brightness", "level": 40}, metadata))
    assert "este computador" in brightness["Alvo"] and "brilho em 40%" in brightness["Alvo"]
    assert brightness["Reversibilidade"].startswith("Reversível")
    invalid = _fields(build_proposal_preview("system_control", {"action": "set_brightness", "level": 400}, metadata))
    assert "inválido" in invalid["Alvo"]
    lock = _fields(build_proposal_preview("system_control", {"action": "lock_screen"}, metadata))
    assert "Bloqueia" in lock["Mudança"] and "senha" in lock["Reversibilidade"]


def test_finance_entry_and_deletion_show_target_amount_and_reversibility():
    metadata = TOOL_CATALOG["finance_tool"]
    add = _fields(build_proposal_preview("finance_tool", {"action": "add", "amount": 50, "category": "Mercado"}, metadata))
    assert "Mercado" in add["Alvo"] and "despesa de R$ 50,00" in add["Alvo"]
    assert add["Reversibilidade"].startswith("Reversível")
    delete = _fields(build_proposal_preview("finance_tool", {"action": "delete", "trans_id": "f1"}, metadata))
    assert "f1" in delete["Alvo"] and delete["Reversibilidade"].startswith("Não reversível")
    assert "não cria permissão permanente" in delete["Escopo"]


def test_whatsapp_shows_recipient_and_message_excerpt_only():
    metadata = TOOL_CATALOG["whatsapp"]
    long_message = "Olá " + "x" * 200
    fields = _fields(build_proposal_preview("whatsapp", {"target": "Maria", "message": long_message}, metadata))
    assert "Maria" in fields["Alvo"] and "mensagem de 204 caracteres" in fields["Alvo"]
    assert "x" * 100 not in fields["Alvo"] and "…" in fields["Alvo"]
    assert fields["Reversibilidade"].startswith("Não reversível")


def test_script_proposal_never_shows_the_code():
    fields = _fields(build_proposal_preview(
        "script_runner", {"language": "powershell", "code": "Remove-Item C:\\segredo", "description": "Limpar a pasta temporária"},
        TOOL_CATALOG["script_runner"],
    ))
    assert "Limpar a pasta temporária" in fields["Alvo"] and "powershell" in fields["Alvo"]
    assert "Remove-Item" not in " ".join(fields.values())


def test_adb_proposal_protects_typed_text_but_shows_shell_command():
    metadata = TOOL_CATALOG["mobile_adb"]
    typed = build_proposal_preview("mobile_adb", {"action": "type_text", "command": "minha-senha"}, metadata)
    assert "minha-senha" not in typed and "11 caracteres" in typed
    shell = _fields(build_proposal_preview("mobile_adb", {"action": "shell", "command": "ls /sdcard"}, metadata))
    assert "ls /sdcard" in shell["Alvo"]


def test_read_only_operations_say_nothing_changes():
    fields = _fields(build_proposal_preview("task_tool", {"action": "list"}, TOOL_CATALOG["task_tool"]))
    assert "nada é alterado" in fields["Mudança"] and fields["Reversibilidade"] == "Nada a desfazer."


def test_tool_without_declarations_uses_metadata_reversible_flag():
    reversible = _fields(build_proposal_preview("x", {}, ToolMetadata(("x",), "low", reversible=True)))
    assert reversible["Reversibilidade"].startswith("Reversível")
    plain = _fields(build_proposal_preview("x", {}, ToolMetadata(("x",), "low")))
    assert "irreversível" in plain["Reversibilidade"]
    assert "esta execução" in plain["Escopo"]
