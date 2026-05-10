# matter_expert — Foundation Library

Foundation library for the matter-expert skill creator.

This library defines the data model and I/O for the Obsidian-compatible
knowledge vault that the matter-expert skill creator builds and consumes.

## Install

```bash
pip install -e ".[dev]"
```

## Public API

### Vault structure
- `VaultPaths(root)` — resolve standard paths inside a vault

### Page types
- `ConceptPage`, `ConceptFrontmatter`, `Source` — the core unit of the vault
- `MOCPage`, `MOCFrontmatter` — Map-of-Content pages (hierarchical overviews)
- `SourcePage`, `SourceFrontmatter` — original-document pages under `vault/sources/`

### Index files (under `_index/`)
- `ConceptIndex` — concept name → location & metadata
- `MOCMap` — MOC hierarchy
- `LinkGraph` — typed links + materialized inverse links
- `AliasMap` — user-facing aliases → canonical concept names

### Validators
- `validate_vault(paths)` — full vault integrity check
- `validate_concept_frontmatter(fm, concept_name)` — single-concept structural check

## Usage

```python
from pathlib import Path
from matter_expert import VaultPaths, ConceptPage, validate_vault

paths = VaultPaths(root=Path("./vault"))
issues = validate_vault(paths)
for issue in issues:
    print(f"[{issue.severity.value}] {issue.location}: {issue.message}")

# Read a concept
page = ConceptPage.read(paths.concept_for("oauth2-flow"))
print(page.frontmatter.title)
print(page.frontmatter.related)  # ['jwt-tokens', 'session-management']
```

## Tests

```bash
pytest
```

## Status

This is Subproject 1 of the matter-expert skill creator.
See `docs/superpowers/specs/2026-05-10-docs-to-skill-design.md` for the full design.
See `docs/superpowers/plans/2026-05-10-foundation.md` for the implementation plan.
