from pathlib import Path

from builder.emit.runtime_bundler import bundle_runtime


def test_bundle_runtime_copies_runtime_package(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert scripts.exists()
    # Runtime is bundled as scripts/runtime/ to preserve the Python package
    # structure needed by `from runtime.xxx import ...` cross-module imports.
    runtime = scripts / "runtime"
    assert runtime.exists(), "scripts/runtime/ package directory must exist"
    assert (runtime / "__init__.py").exists()
    assert (runtime / "index.py").exists()
    assert (runtime / "memory.py").exists()
    assert (runtime / "vault_locate.py").exists()
    assert (runtime / "vault_search.py").exists()
    assert (runtime / "vault_traverse.py").exists()
    assert (runtime / "vault_brainstorm.py").exists()
    assert (runtime / "vault_cite.py").exists()
    assert (runtime / "memory_update.py").exists()
    assert (runtime / "memory_inspect.py").exists()


def test_bundle_runtime_does_not_copy_pycache(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert not list(scripts.rglob("__pycache__"))
    assert not list(scripts.rglob("*.pyc"))


def test_bundle_runtime_is_idempotent(tmp_path: Path):
    """Calling bundle_runtime twice into the same dir must not raise."""
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)
    bundle_runtime(plugin_skill_dir)  # second call — must not raise

    scripts = plugin_skill_dir / "scripts"
    assert (scripts / "runtime" / "vault_locate.py").exists()
