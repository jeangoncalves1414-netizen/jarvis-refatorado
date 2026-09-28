import sys
from pathlib import Path
import pytest

# Ensure the repository root is on sys.path so tests can import the `app` package
ROOT = Path(__file__).parent.parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


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
