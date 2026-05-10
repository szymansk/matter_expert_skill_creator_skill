"""Generate the README.md for the produced expert-skill plugin."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReadmeMeta:
    plugin_name: str
    version: str
    description: str
    concept_count: int
    moc_count: int


README_TEMPLATE = """\
# {plugin_name}

**Version:** {version}

{description}

## What's bundled

- **{concept_count} concepts** in `skills/{plugin_name}/vault/concepts/`
- **{moc_count} Maps of Content** in `skills/{plugin_name}/vault/MOCs/`
- Pre-built JSON indexes in `skills/{plugin_name}/_index/`
- Stdlib-only runtime scripts in `skills/{plugin_name}/scripts/`

## Install

Drop this plugin into your Claude Code plugin directory:

```
~/.claude/plugins/{plugin_name}/
```

Restart Claude Code and the skill auto-loads. Ask any question on the
covered topics and the skill triggers.

## How it works

The skill uses a four-layer retrieval pipeline (locate → search → traverse →
synthesize) backed by the bundled vault. Citations are sourced from the
original documents recorded in each concept's frontmatter.
"""


def generate_readme(plugin_root: Path, meta: ReadmeMeta) -> Path:
    plugin_root.mkdir(parents=True, exist_ok=True)
    path = plugin_root / "README.md"
    path.write_text(
        README_TEMPLATE.format(
            plugin_name=meta.plugin_name,
            version=meta.version,
            description=meta.description,
            concept_count=meta.concept_count,
            moc_count=meta.moc_count,
        ),
        encoding="utf-8",
    )
    return path
