"""Fixtures for runtime/ tests.

The fixtures here use matter_expert (Subproject 1) to build realistic
JSON indexes from the example vault. Production runtime code itself
never imports matter_expert — only test infrastructure does.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from builder.emit.index_builder import build_indexes
from matter_expert import VaultPaths


@dataclass(frozen=True)
class IndexBundle:
    """The set of paths to the JSON index files used at runtime."""

    index_dir: Path
    concept_index: Path
    moc_map: Path
    link_graph: Path
    alias_map: Path
    bm25_index: Path


@pytest.fixture
def vault_dir(example_vault_paths: VaultPaths) -> Path:
    """Return the example vault root directory (alias for clarity)."""
    return example_vault_paths.root


@pytest.fixture
def built_indexes(tmp_path: Path, example_vault_paths: VaultPaths) -> IndexBundle:
    """Build all JSON indexes from the example vault into tmp_path/_index.

    Delegates to the Builder's Emit phase (``build_indexes``) so the fixture
    always mirrors the real production output — including ``bm25_index.json`` —
    rather than re-implementing index construction.
    """
    index_dir = tmp_path / "_index"
    build_indexes(example_vault_paths, index_dir)

    return IndexBundle(
        index_dir=index_dir,
        concept_index=index_dir / "concept_index.json",
        moc_map=index_dir / "moc_map.json",
        link_graph=index_dir / "link_graph.json",
        alias_map=index_dir / "alias_map.json",
        bm25_index=index_dir / "bm25_index.json",
    )


@pytest.fixture
def memory_dir(tmp_path: Path) -> Path:
    """Return a fresh empty memory directory under tmp_path/memory."""
    d = tmp_path / "memory"
    d.mkdir()
    return d
