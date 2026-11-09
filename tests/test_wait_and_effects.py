"""Rotinas, fase 1: espera real entre ações (ferramenta wait) e verificação de efeito."""
from types import SimpleNamespace

import pytest

from app.agent import effect_checks
from app.agent.action_executor import ActionExecutor
from app.agent.tool_guardrails import ToolCallGuardrailController
from app.agent.tools.base import ToolResult
from app.agent.tools.catalog import TOOL_CATALOG
from app.agent.tools.wait import TOO_LONG_TEXT, WaitTool
from app.core import waits
from app.core.runs import RunCancelled, current_run
from app.storage.action_store import ActionStore


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = 0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps += 1
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(waits, "_monotonic", fake.monotonic)
    monkeypatch.setattr(waits, "_sleep", fake.sleep)
    monkeypatch.setattr(effect_checks, "_monotonic", fake.monotonic)
    monkeypatch.setattr(effect_checks, "_sleep", fake.sleep)
    return fake


@pytest.fixture
def store(tmp_path):
    journal = ActionStore(tmp_path / "journal.sqlite3")
    yield journal
    if journal._runtime_lock:
        journal._runtime_lock.close()


def executor_for(store, tools, metadata=None):
    """ActionExecutor com ferramentas reais ou falsas (``tools``: nome -> objeto com ``execute``)."""
    def legacy(name, args, _user):
        return tools[name].execute(args)
    return ActionExecutor(frozenset(tools), ToolCallGuardrailController(), legacy,
                          metadata_for=metadata or TOOL_CATALOG.get, store=store, source="test")


# ── espera ──────────────────────────────────────────────────────────────────
def test_wait_reports_every_second_down_to_zero(clock):
    reported = []
    token = waits.current_wait_reporter.set(lambda remaining, total: reported.append((remaining, total)))
    try:
        assert waits.wait_seconds(3) == 3
    finally:
        waits.current_wait_reporter.reset(token)
    assert reported == [(3, 3), (2, 3), (1, 3), (0, 3)]
    assert clock.now == pytest.approx(3.0) and clock.sleeps == 6


def test_wait_without_reporter_updates_run_progress(clock, store):
    run = store.create_run(session_id="s1", mode="general")
    token = current_run.set((store, run.id))
    try:
        waits.wait_seconds(2, label="teste")
    finally:
        current_run.reset(token)
    progress = store.run_details(run.id)["run"]["progress"]
    assert progress["phase"] == "waiting" and progress["wait_remaining"] == 0 and progress["wait_total"] == 2


def test_cancel_during_wait_raises_and_marks_the_action_cancelled(clock, store, monkeypatch):
    run = store.create_run(session_id="s1", mode="general")

    def sleep_then_cancel(seconds):
        clock.sleep(seconds)
        if clock.now >= 1.0:
            store.cancel_run(run.id)
    monkeypatch.setattr(waits, "_sleep", sleep_then_cancel)
    token = current_run.set((store, run.id))
    try:
        executor = executor_for(store, {"wait": WaitTool()})
        with pytest.raises(RunCancelled):
            executor.execute("wait", {"seconds": 50}, "espera 50 s")
        action = executor.last_action
    finally:
        current_run.reset(token)
    assert action.status == "cancelled" and action.result_summary == "Pedido cancelado durante a execução."
    assert clock.now < 2.0  # parou logo, sem esperar os 50 s


def test_wait_longer_than_one_hour_asks_for_a_routine(clock):
    result = WaitTool().execute({"seconds": 3601})
    assert result.ok is False and result.message == TOO_LONG_TEXT and "rotina" in result.message
    assert WaitTool().execute({"seconds": 0}).ok is False
    assert WaitTool().execute({"seconds": "abc"}).ok is False
    assert clock.sleeps == 0
    done = WaitTool().execute({"seconds": 2, "reason": "antes do YouTube"})
    assert done.ok and done.message == "Esperei 2 s (antes do YouTube)." and clock.now == pytest.approx(2.0)


def test_wait_is_low_risk_and_timer_says_it_does_not_wait():
    from app.agent.tools.timer import TimerTool
    assert TOOL_CATALOG["wait"].risk_for({"seconds": 5}) == "low"
    assert "nada é alterado" in TOOL_CATALOG["wait"].effect_for({"seconds": 5})
    assert "NÃO pausa" in TimerTool().description and "wait" in TimerTool().description
    assert "Parar pedido" in WaitTool().description and "timer" in WaitTool().description


def test_wait_is_registered_for_chat_and_loop(tmp_path):
    from app.agent.react_loop import REACT_TOOLS
    from app.agent.tools.registry import LOOP_DATA_TOOLS, ToolRegistry
    registry = ToolRegistry(base_folder=str(tmp_path))
    assert "wait" in registry.tools and "wait" in LOOP_DATA_TOOLS and "wait" in REACT_TOOLS
    assert "wait" in registry.allowed_tool_names(mode="general", provider="groq", user_text="oi")
    assert "wait" in registry.allowed_tool_names(mode="general", provider="gemini", user_text="abre o spotify", narrow=True)


# ── verificação de efeito ───────────────────────────────────────────────────
@pytest.fixture
def probes(monkeypatch, clock):
    """Liga a verificação com sondas falsas; ``state`` controla o que o "Windows" mostra."""
    state = SimpleNamespace(processes=[], titles=[], spotify=[], calls=0)
    monkeypatch.setattr(effect_checks, "enabled", True)

    def processes():
        state.calls += 1
        value = state.processes[min(state.calls, len(state.processes)) - 1] if state.processes else set()
        return set(value)

    monkeypatch.setattr(effect_checks, "_processes", processes)
    monkeypatch.setattr(effect_checks, "_window_titles", lambda: list(state.titles))
    monkeypatch.setattr(effect_checks, "_spotify_title", lambda: state.spotify.pop(0) if len(state.spotify) > 1 else (state.spotify[0] if state.spotify else ""))
    return state


class Fixed:
    def __init__(self, result):
        self.result = result

    def execute(self, _args):
        return self.result


def test_app_process_appearing_on_third_poll_is_confirmed(probes, store):
    probes.processes = [set(), set(), {"spotify.exe"}]
    executor = executor_for(store, {"open_windows_app": Fixed(ToolResult(True, "Aplicativo 'spotify' aberto com sucesso."))})
    message = executor.execute("open_windows_app", {"action": "open", "app_name": "spotify"}, "abre o spotify")
    action = executor.last_action
    assert probes.calls == 3
    assert action.status == "succeeded"
    assert "Confirmado: processo spotify.exe em execução." in message
    assert "Confirmado" in action.result_summary
    # Processo e janela juntos entram na evidência.
    probes.calls, probes.titles = 0, ["Spotify Premium"]
    probes.processes = [{"spotify.exe"}]
    check = effect_checks.check_effect("open_windows_app", {"action": "open", "app_name": "spotify"}, ToolResult(True, "ok"))
    assert check.evidence == 'processo spotify.exe, janela "Spotify Premium"'


def test_app_that_never_appears_stays_succeeded_but_unconfirmed(probes, store, clock):
    result = ToolResult(True, "Aplicativo 'notepad' aberto com sucesso.")
    executor = executor_for(store, {"open_windows_app": Fixed(result)})
    message = executor.execute("open_windows_app", {"action": "open", "app_name": "notepad"}, "abre o bloco de notas")
    assert executor.last_action.status == "succeeded"
    assert "não consegui confirmar" in message and "não consegui confirmar" in executor.last_action.result_summary
    assert result.data["effect"]["status"] == "unconfirmed"
    assert clock.now >= effect_checks.APP_TIMEOUT


def test_already_running_app_is_confirmed_without_polling(probes):
    check = effect_checks.check_effect("open_windows_app", {"action": "open", "app_name": "chrome"}, ToolResult(True, "ok", data={"already_running": True}))
    assert check.status == "confirmed" and "já estava aberto" in check.evidence and probes.calls == 0


def test_spotify_search_play_confirmed_by_window_title(probes):
    probes.spotify = ["Spotify Premium", "Spotify Premium", "Lofi Girl - Snowman"]
    check = effect_checks.check_effect("spotify", {"action": "search_play", "query": "lofi"}, ToolResult(True, "Busquei"))
    assert check.status == "confirmed" and "Lofi Girl - Snowman" in check.evidence
    probes.spotify = ["Spotify Premium"]
    assert effect_checks.check_effect("spotify", {"action": "search_play", "query": "x"}, ToolResult(True, "x")).status == "unconfirmed"


def test_spotify_control_compares_title_before_and_after(probes):
    probes.spotify = ["Artista - Música 1"]
    before = effect_checks.capture_before("spotify", {"action": "next"})
    probes.spotify = ["Artista - Música 2"]
    assert effect_checks.check_effect("spotify", {"action": "next"}, ToolResult(True, "ok"), before).status == "confirmed"
    probes.spotify = ["Artista - Música 1"]
    assert effect_checks.check_effect("spotify", {"action": "next"}, ToolResult(True, "ok"), before).status == "unconfirmed"


def test_youtube_video_in_browser_window_is_confirmed_as_opened(probes):
    probes.processes = [{"chrome.exe"}]
    probes.titles = ["Lofi - YouTube - Google Chrome"]
    url = "https://www.youtube.com/watch?v=abc"
    check = effect_checks.check_effect("web_search", {"action": "open_url", "query": url}, ToolResult(True, "ok", data={"url": url}))
    assert check.status == "confirmed" and "abri o vídeo" in check.evidence and "não consigo confirmar que está tocando" in check.evidence
    probes.titles = ["YouTube - Google Chrome"]
    plain = effect_checks.check_effect("web_search", {"action": "open_url", "query": url}, ToolResult(True, "ok", data={"url": url}))
    assert plain.status == "unconfirmed"
    probes.processes = [set()]
    assert effect_checks.check_effect("web_search", {"action": "open_url", "query": url}, ToolResult(True, "ok")).status == "unconfirmed"


def test_data_tools_are_not_applicable(probes, store):
    result = ToolResult(True, "2 hábitos criados")
    executor = executor_for(store, {"habit_tool": Fixed(result)})
    message = executor.execute("habit_tool", {"action": "list"}, "lista")
    assert message == "2 hábitos criados" and "effect" not in result.data and probes.calls == 0


def test_probe_exception_never_breaks_the_action(probes, store, monkeypatch):
    def broken():
        raise OSError("sem acesso")
    monkeypatch.setattr(effect_checks, "_processes", broken)
    result = ToolResult(True, "Aplicativo 'spotify' aberto com sucesso.")
    executor = executor_for(store, {"open_windows_app": Fixed(result)})
    message = executor.execute("open_windows_app", {"action": "open", "app_name": "spotify"}, "abre")
    assert executor.last_action.status == "succeeded" and message == "Aplicativo 'spotify' aberto com sucesso."
    assert "effect" not in result.data


def test_checks_are_off_by_default_in_tests():
    assert effect_checks.enabled is False
    assert effect_checks.check_effect("spotify", {"action": "open"}, ToolResult(True, "ok")).status == "not_applicable"
