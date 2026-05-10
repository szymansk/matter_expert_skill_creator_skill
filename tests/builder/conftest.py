from pathlib import Path

import pytest


@pytest.fixture
def run_dir(tmp_path: Path) -> Path:
    """A fresh per-run state directory under tmp_path/run."""
    d = tmp_path / "run"
    d.mkdir()
    return d
