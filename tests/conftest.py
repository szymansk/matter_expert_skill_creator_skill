from pathlib import Path

import pytest

from matter_expert.paths import VaultPaths

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_vault_paths() -> VaultPaths:
    """The example vault checked in under tests/fixtures/."""
    return VaultPaths(root=FIXTURES_DIR / "example_vault")
