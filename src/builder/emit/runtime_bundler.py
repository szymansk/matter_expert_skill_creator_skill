"""Copy the runtime package into the generated plugin's scripts/ directory."""
from __future__ import annotations

import shutil
from pathlib import Path


def _find_runtime_source() -> Path:
    """Locate the `src/runtime/` directory of the current matter_expert checkout."""
    # __file__ is .../matter_expert_skill_creator_skill/src/builder/emit/runtime_bundler.py
    # Climb up to src/ then descend into runtime/.
    here = Path(__file__).resolve()
    src_dir = here.parent.parent.parent  # src/
    runtime = src_dir / "runtime"
    if not runtime.is_dir():
        raise RuntimeError(f"runtime source not found at {runtime}")
    return runtime


def bundle_runtime(plugin_skill_dir: Path) -> Path:
    """Copy the runtime package into `<plugin_skill_dir>/scripts/runtime/`.

    The runtime scripts import each other as ``from runtime.xxx import ...``.
    Preserving the ``runtime/`` package directory under ``scripts/`` keeps those
    imports resolvable when Python is invoked from any working directory:
    the per-script sys.path bootstrap (see each runtime module) adds
    ``scripts/`` to ``sys.path``, making ``import runtime`` resolve correctly.

    Returns the scripts/ directory path. Excludes __pycache__ and *.pyc.
    """
    runtime_src = _find_runtime_source()
    scripts = plugin_skill_dir / "scripts"
    scripts.mkdir(parents=True, exist_ok=True)

    def _ignore(_dir: str, names: list[str]) -> list[str]:
        return [n for n in names if n == "__pycache__" or n.endswith(".pyc")]

    # Copy the entire runtime/ tree as scripts/runtime/ so that
    # `from runtime.index import ...` resolves when scripts/ is on sys.path.
    dest_runtime = scripts / "runtime"
    shutil.copytree(
        runtime_src, dest_runtime,
        dirs_exist_ok=True, ignore=_ignore,
    )
    return scripts
