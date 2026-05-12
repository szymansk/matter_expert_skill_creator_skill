import json
from pathlib import Path

from builder.emit.plugin_metadata import (
    PluginMetadata,
    write_marketplace_json,
    write_plugin_json,
)


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
    # Must declare the skills directory so Claude Code auto-discovers SKILL.md files.
    assert data["skills"] == "./skills"


def test_write_plugin_json_author_is_object(tmp_path: Path):
    """author must be an object {name: ...} matching the Claude Code manifest schema."""
    meta = PluginMetadata(name="x", version="0.1.0", description="d", author="alice")
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_plugin_json(meta, plugin_root)
    data = json.loads(
        (plugin_root / ".claude-plugin" / "plugin.json").read_text()
    )
    assert isinstance(data["author"], dict)
    assert data["author"]["name"] == "alice"


def test_write_marketplace_json_creates_file(tmp_path: Path):
    """The marketplace.json sits at .claude-plugin/marketplace.json so that
    /plugin marketplace add github-user/repo installs the produced plugin."""
    meta = PluginMetadata(
        name="oauth-expert", version="0.1.0",
        description="OAuth knowledge.", author="alice",
    )
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_marketplace_json(meta, plugin_root)

    mp = plugin_root / ".claude-plugin" / "marketplace.json"
    assert mp.exists()
    data = json.loads(mp.read_text(encoding="utf-8"))
    assert data["name"] == "oauth-expert"
    assert data["owner"]["name"] == "alice"
    assert len(data["plugins"]) == 1
    assert data["plugins"][0]["name"] == "oauth-expert"
    assert data["plugins"][0]["version"] == "0.1.0"
    assert data["plugins"][0]["source"] == "./"


def test_write_marketplace_json_plugin_author_is_object(tmp_path: Path):
    meta = PluginMetadata(name="x", version="0.1.0", description="d", author="alice")
    plugin_root = tmp_path / "plugin"
    plugin_root.mkdir()
    write_marketplace_json(meta, plugin_root)
    data = json.loads(
        (plugin_root / ".claude-plugin" / "marketplace.json").read_text()
    )
    assert isinstance(data["plugins"][0]["author"], dict)
    assert data["plugins"][0]["author"]["name"] == "alice"
