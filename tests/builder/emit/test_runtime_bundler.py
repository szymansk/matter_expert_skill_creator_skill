from pathlib import Path

from builder.emit.runtime_bundler import bundle_runtime


def test_bundle_runtime_copies_runtime_package(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert scripts.exists()
    # Some key runtime modules
    assert (scripts / "index.py").exists()
    assert (scripts / "memory.py").exists()
    assert (scripts / "vault_locate.py").exists()
    assert (scripts / "vault_search.py").exists()
    assert (scripts / "vault_traverse.py").exists()
    assert (scripts / "vault_brainstorm.py").exists()
    assert (scripts / "vault_cite.py").exists()
    assert (scripts / "memory_update.py").exists()
    assert (scripts / "memory_inspect.py").exists()


def test_bundle_runtime_does_not_copy_pycache(tmp_path: Path):
    plugin_skill_dir = tmp_path / "skills" / "my-skill"
    bundle_runtime(plugin_skill_dir)

    scripts = plugin_skill_dir / "scripts"
    assert not list(scripts.glob("__pycache__"))
    assert not list(scripts.rglob("*.pyc"))
