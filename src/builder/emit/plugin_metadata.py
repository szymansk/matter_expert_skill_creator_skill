"""Plugin metadata + plugin.json writer."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PluginMetadata:
    name: str
    version: str
    description: str
    author: str
    homepage: str | None = None
    license: str = "Apache-2.0"


def write_plugin_json(meta: PluginMetadata, plugin_root: Path) -> Path:
    """Write `<plugin_root>/.claude-plugin/plugin.json` and return its path."""
    plugin_dir = plugin_root / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "plugin.json"
    data: dict = {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "author": meta.author,
        "license": meta.license,
    }
    if meta.homepage:
        data["homepage"] = meta.homepage
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
