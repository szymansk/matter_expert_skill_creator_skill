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
    """Write `<plugin_root>/.claude-plugin/plugin.json` and return its path.

    The ``author`` field is written as ``{"name": "..."}`` (object form) to
    match the Claude Code plugin manifest schema.  The ``skills`` key points
    to ``./skills`` so Claude Code auto-discovers all ``skills/*/SKILL.md``
    files on install.
    """
    plugin_dir = plugin_root / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "plugin.json"
    data: dict = {
        "name": meta.name,
        "version": meta.version,
        "description": meta.description,
        "author": {"name": meta.author},
        "license": meta.license,
        "skills": "./skills",
    }
    if meta.homepage:
        data["homepage"] = meta.homepage
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def write_marketplace_json(meta: PluginMetadata, plugin_root: Path) -> Path:
    """Write `<plugin_root>/.claude-plugin/marketplace.json` and return its path.

    The marketplace.json declares this directory as a single-plugin marketplace
    so Claude Code's ``/plugin marketplace add <github-user>/<repo>`` flow
    can install it directly from GitHub.  The plugin's source is the marketplace
    root itself (``"./"``).
    """
    plugin_dir = plugin_root / ".claude-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    path = plugin_dir / "marketplace.json"
    data: dict = {
        "name": meta.name,
        "description": meta.description,
        "owner": {"name": meta.author},
        "plugins": [
            {
                "name": meta.name,
                "description": meta.description,
                "version": meta.version,
                "author": {"name": meta.author},
                "source": "./",
            },
        ],
    }
    path.write_text(
        json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
    return path
