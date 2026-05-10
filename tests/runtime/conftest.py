"""Fixtures for runtime/ tests.

The fixtures here use matter_expert (Subproject 1) to build realistic
JSON indexes from the example vault. Production runtime code itself
never imports matter_expert — only test infrastructure does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from matter_expert import (
    AliasMap,
    ConceptIndex,
    ConceptIndexEntry,
    ConceptPage,
    LinkGraph,
    MOCMap,
    MOCMapEntry,
    MOCPage,
    VaultPaths,
)


@dataclass(frozen=True)
class IndexBundle:
    """The set of paths to the 4 JSON index files used at runtime."""

    index_dir: Path
    concept_index: Path
    moc_map: Path
    link_graph: Path
    alias_map: Path


@pytest.fixture
def vault_dir(example_vault_paths: VaultPaths) -> Path:
    """Return the example vault root directory (alias for clarity)."""
    return example_vault_paths.root


@pytest.fixture
def built_indexes(tmp_path: Path, example_vault_paths: VaultPaths) -> IndexBundle:
    """Build all 4 JSON indexes from the example vault into tmp_path/_index.

    Uses matter_expert to read the vault and serialize indexes. The result
    matches what the Builder's Emit phase (Subproject 8) will produce.
    """
    index_dir = tmp_path / "_index"
    index_dir.mkdir()

    # Load all concept pages from the example vault.
    concept_pages: dict[str, ConceptPage] = {}
    for path in sorted(example_vault_paths.concepts.glob("*.md")):
        page = ConceptPage.read(path)
        concept_pages[page.name] = page

    # Build ConceptIndex (concept_name -> ConceptIndexEntry)
    concept_index = ConceptIndex({
        name: ConceptIndexEntry(
            path=f"concepts/{name}.md",
            title=page.frontmatter.title,
            summary=page.body.split("\n", 2)[-1].strip()[:120],
            tags=list(page.frontmatter.tags),
            aliases=[],  # example vault has no aliases yet
            moc=[],
        )
        for name, page in concept_pages.items()
    })
    concept_index.write(index_dir / "concept_index.json")

    # Build MOCMap from the MOC pages.
    moc_pages: dict[str, MOCPage] = {}
    for path in sorted(example_vault_paths.mocs.glob("*.md")):
        page = MOCPage.read(path)
        moc_pages[page.name] = page

    moc_map = MOCMap({
        name: MOCMapEntry(
            path=f"MOCs/{name}.md",
            children=list(page.frontmatter.children),
            parents=list(page.frontmatter.parents),
        )
        for name, page in moc_pages.items()
    })
    moc_map.write(index_dir / "moc_map.json")

    # Build LinkGraph (with materialized inverse links).
    link_graph = LinkGraph.build({
        name: page.frontmatter for name, page in concept_pages.items()
    })
    link_graph.write(index_dir / "link_graph.json")

    # Build AliasMap from concept aliases.
    alias_map = AliasMap.build(concept_index)
    alias_map.write(index_dir / "alias_map.json")

    return IndexBundle(
        index_dir=index_dir,
        concept_index=index_dir / "concept_index.json",
        moc_map=index_dir / "moc_map.json",
        link_graph=index_dir / "link_graph.json",
        alias_map=index_dir / "alias_map.json",
    )


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Return a fresh empty memory directory under tmp_path/memory."""
    d = tmp_path / "memory"
    d.mkdir()
    return d
