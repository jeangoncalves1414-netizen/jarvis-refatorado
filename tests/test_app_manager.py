from unittest.mock import patch
from app.services.app_manager import AppManager


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

