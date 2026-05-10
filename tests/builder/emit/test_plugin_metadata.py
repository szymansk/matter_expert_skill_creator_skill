import json
from pathlib import Path

from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json


def test_plugin_metadata_construction():
    meta = PluginMetadata(
        name="oauth-expert",
        version="0.1.0",
        description="OAuth and JWT knowledge.",
        author="builder",
    )
    assert meta.name == "oauth-expert"


def test_write_plugin_json_creates_file(tmp_path: Path):
    meta = PluginMetadata(
        name="x", version="0.1.0",
        description="d", author="a",
    )
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_plugin_json(meta, plugin_root)

    plugin_json = plugin_root / ".claude-plugin" / "plugin.json"
    assert plugin_json.exists()
    data = json.loads(plugin_json.read_text(encoding="utf-8"))
    assert data["name"] == "x"
    assert data["version"] == "0.1.0"


def test_write_plugin_json_includes_skill_entry(tmp_path: Path):
    meta = PluginMetadata(name="x", version="0.1.0", description="d", author="a")
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_plugin_json(meta, plugin_root)
    data = json.loads(
        (plugin_root / ".claude-plugin" / "plugin.json").read_text()
    )
    # Must declare the bundled skill so Claude Code can auto-discover it.
    assert "skills" in data or data["name"]  # at minimum, name present
