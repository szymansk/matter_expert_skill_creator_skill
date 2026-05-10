from pathlib import Path

from builder.emit.readme import generate_readme, ReadmeMeta


def test_generate_readme_writes_file(tmp_path: Path):
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()

    meta = ReadmeMeta(
        plugin_name="my-skill", version="0.1.0",
        description="Expert on OAuth.",
        concept_count=42, moc_count=5,
    )
    path = generate_readme(plugin_root=plugin_root, meta=meta)

    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "my-skill" in content
    assert "42" in content
    assert "OAuth" in content
    assert "install" in content.lower()
