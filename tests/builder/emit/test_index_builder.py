import json
from datetime import date
from pathlib import Path

from builder.emit.index_builder import build_indexes
from matter_expert import ConceptFrontmatter, ConceptPage, Source, VaultPaths


def _seed(paths: VaultPaths, name: str, title: str, tags=None,
          aliases=None, related=None, prereq=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}-source.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
        related=list(related or []),
        prerequisites=list(prereq or []),
    )
    paths.concepts.mkdir(parents=True, exist_ok=True)
    ConceptPage(
        frontmatter=fm,
        body=f"# {title}\n\nSummary of {title}.\n",
        path=paths.concept_for(name),
    ).write()


def test_build_indexes_writes_all_four_files(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    _seed(paths, "oauth2-flow", "OAuth2 Flow", tags=["auth"], related=["jwt-tokens"])
    _seed(paths, "jwt-tokens", "JWT", tags=["auth"], prereq=["oauth2-flow"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    assert (index_dir / "concept_index.json").exists()
    assert (index_dir / "moc_map.json").exists()
    assert (index_dir / "link_graph.json").exists()
    assert (index_dir / "alias_map.json").exists()


def test_build_indexes_concept_index_contains_seeded_concepts(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()
    _seed(paths, "x", "Concept X", tags=["t"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    data = json.loads((index_dir / "concept_index.json").read_text())
    assert "x" in data
    assert data["x"]["title"] == "Concept X"


def test_build_indexes_link_graph_materializes_inverse(tmp_path: Path):
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()
    _seed(paths, "a", "A")
    _seed(paths, "b", "B", prereq=["a"])

    index_dir = tmp_path / "vault" / "_index"
    build_indexes(vault=paths, index_dir=index_dir)

    graph = json.loads((index_dir / "link_graph.json").read_text())
    # b depends on a → a "leads_to" b
    assert "b" in graph["a"]["leads_to"]
