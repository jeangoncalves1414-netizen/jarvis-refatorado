from pathlib import Path
import pytest

from app.domain.actions import FileActionService


def test_file_action_service_lists_directory(tmp_path: Path) -> None:
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "todo.txt").write_text("hello", encoding="utf-8")

    service = FileActionService(base_folder=str(tmp_path))
    result = service.execute("liste os arquivos da pasta notes")

    assert result["kind"] == "directory"
    assert "todo.txt" in result["items"]


def test_directory_boundary_rejects_sibling_with_same_prefix(tmp_path: Path):
    root = tmp_path / "workspace"
    sibling = tmp_path / "workspace-private"
    root.mkdir()
    sibling.mkdir()
    service = FileActionService(str(root))
    with pytest.raises(ValueError):
        service.execute("Liste os arquivos da pasta ../workspace-private")
