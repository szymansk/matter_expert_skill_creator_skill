import os
from pathlib import Path

import pytest

# The bundled packages live inside the plugin (scripts/lib/). pytest's
# `pythonpath` setting makes them importable in-process, but tests that spawn a
# subprocess (`python -m runtime.X` / `python -m builder.X`) need the path on the
# child's environment too. Put it on PYTHONPATH so those subprocesses resolve the
# packages — this mirrors exactly how the shipped plugin invokes them, i.e.
# `PYTHONPATH=${CLAUDE_SKILL_DIR}/scripts/lib python3 -m ...`.
_LIB = (
    Path(__file__).resolve().parent.parent
    / "docs-to-skill" / "skills" / "docs-to-skill" / "scripts" / "lib"
)
_existing = os.environ.get("PYTHONPATH", "")
if str(_LIB) not in _existing.split(os.pathsep):
    os.environ["PYTHONPATH"] = (
        os.pathsep.join([str(_LIB), _existing]) if _existing else str(_LIB)
    )

from matter_expert.paths import VaultPaths

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def example_vault_paths() -> VaultPaths:
    """The example vault checked in under tests/fixtures/."""
    return VaultPaths(root=FIXTURES_DIR / "example_vault")
