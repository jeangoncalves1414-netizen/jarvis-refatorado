from app.ui.panel.app import PanelApp


def test_panel_app_renders_snapshot_context() -> None:
    panel = PanelApp()
    html = panel.render(status="online", task_count=2, memory_count=1, last_summary="Resumo do agente")

    assert "online" in html.lower()
    assert "2" in html
    assert "1" in html
    assert "Resumo do agente" in html
