"""Verifies the conftest fixtures provide what runtime tests need."""
import json
from pathlib import Path


def test_built_indexes_fixture_provides_all_four_files(built_indexes):
    """The fixture must return paths to all 4 index JSON files."""
    assert built_indexes.concept_index.exists()
    assert built_indexes.moc_map.exists()
    assert built_indexes.link_graph.exists()
    assert built_indexes.alias_map.exists()


def test_built_indexes_concept_index_contains_example_vault_concepts(built_indexes):
    raw = json.loads(built_indexes.concept_index.read_text(encoding="utf-8"))
    assert "oauth2-flow" in raw
    assert raw["oauth2-flow"]["title"] == "OAuth2 Flow"


def test_built_indexes_link_graph_has_inverse_links(built_indexes):
    """The Subproject 1 LinkGraph.build() materializes inverse links.
    Verify oauth2-flow's prerequisites lead-to it from http-basics."""
    raw = json.loads(built_indexes.link_graph.read_text(encoding="utf-8"))
    assert "oauth2-flow" in raw["http-basics"]["leads_to"]


def test_built_indexes_alias_map_resolves_oauth(built_indexes):
    """AliasMap.build() inverts ConceptIndex.aliases. The example vault
    has no aliases set, so the alias map should be empty."""
    raw = json.loads(built_indexes.alias_map.read_text(encoding="utf-8"))
    assert raw == {}


def test_memory_dir_fixture_provides_empty_directory(memory_dir: Path):
    """The memory_dir fixture creates a fresh, empty memory directory."""
    assert memory_dir.exists()
    assert memory_dir.is_dir()
    assert list(memory_dir.iterdir()) == []


def test_vault_dir_fixture_points_to_example_vault(vault_dir: Path):
    """The vault_dir fixture exposes the example vault root for ripgrep tests."""
    assert (vault_dir / "concepts" / "oauth2-flow.md").exists()
