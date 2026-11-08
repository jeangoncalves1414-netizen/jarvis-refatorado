from unittest.mock import MagicMock, patch

import pytest

from app.services.app_manager import AppManager


@pytest.fixture(autouse=True)
def _empty_registry(monkeypatch):
    """O registro do Windows nunca é lido nestes testes."""
    monkeypatch.setattr(AppManager, "_scan_registry", lambda self: {})


def test_app_manager_find_app():
    am = AppManager()
    assert am.find_app("spotify") in ("spotify", "spotify.exe")
    assert am.find_app("bloco de notas") in ("notepad", "notepad.exe")


def test_app_manager_open_app_uri():
    am = AppManager()
    with patch("subprocess.Popen") as mock_popen, patch("os.startfile") as mock_start:
        res = am.open_app("spotify")
        assert res is True
        assert mock_popen.called or mock_start.called


def test_app_manager_open_app_system():
    am = AppManager()
    with patch("subprocess.Popen") as mock_popen, patch.object(am, "is_app_running", return_value=(False, [])):
        res = am.open_app("calc")
        assert res is True
        mock_popen.assert_called_once()
        argv = mock_popen.call_args.args[0]
        assert isinstance(argv, list) and argv[0].lower().endswith("calc.exe")
        assert mock_popen.call_args.kwargs["shell"] is False


@pytest.mark.parametrize("name", ["cmd /c echo x", "notepad && calc", "powershell -c whoami", "x | calc"])
def test_open_app_never_hands_free_text_to_the_shell(name):
    am = AppManager()
    with patch("subprocess.Popen") as mock_popen, patch("os.startfile") as mock_start:
        assert am.open_app(name) is False
    mock_popen.assert_not_called()
    mock_start.assert_not_called()


def _procs(*names):
    return [MagicMock(info={"pid": index, "name": name}) for index, name in enumerate(names)]


def test_is_app_running_matches_exact_executable_name():
    am = AppManager()
    procs = _procs("notepad.exe", "Notepad.EXE", "notepad++.exe", "note.exe", "code.exe")
    with patch("psutil.process_iter", side_effect=lambda *_a, **_k: iter(procs)):
        running, matches = am.is_app_running("bloco de notas")
        assert running is True
        assert matches == procs[:2]
        assert am.is_app_running("note")[1] == [procs[3]]
        assert am.is_app_running("Code.exe")[1] == [procs[4]]
        assert am.is_app_running("pad") == (False, [])
        assert am.is_app_running("") == (False, [])


def test_close_app_only_stops_exact_matches():
    am = AppManager()
    procs = _procs("notepad.exe", "notepad++.exe")
    with patch("psutil.process_iter", side_effect=lambda *_a, **_k: iter(procs)), patch("time.sleep"):
        ok, _message = am.close_app("notepad")
    assert ok is True
    procs[0].terminate.assert_called_once()
    procs[1].terminate.assert_not_called()
    procs[1].kill.assert_not_called()


def test_app_manager_close_app_not_running():
    am = AppManager()
    with patch.object(am, "is_app_running", return_value=(False, [])):
        ok, msg = am.close_app("non_existent_app_12345")
        assert ok is False
        assert "não está em execução" in msg


def test_open_windows_app_tool_actions():
    from app.agent.tools.open_windows_app import OpenWindowsAppTool
    tool = OpenWindowsAppTool()
    
    # Test close action when app not running
    with patch.object(tool.app_manager, "is_app_running", return_value=(False, [])):
        res_close = tool.execute({"action": "close", "app_name": "notepad"})
        assert res_close.ok is False
        assert "não está em execução" in res_close.message

    # Test open action when app already running
    with patch.object(tool.app_manager, "is_app_running", return_value=(True, [None])), \
         patch.object(tool.app_manager, "focus_window", return_value=True):
        res_open = tool.execute({"action": "open", "app_name": "notepad"})
        assert res_open.ok is True
        assert "já está aberto" in res_open.message

