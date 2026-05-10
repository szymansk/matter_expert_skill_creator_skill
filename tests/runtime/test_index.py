from pathlib import Path

from runtime.index import (
    IndexPaths,
    load_alias_map,
    load_concept_index,
    load_link_graph,
    load_moc_map,
)


def test_index_paths_resolution():
    paths = IndexPaths(index_dir=Path("/tmp/idx"))
    assert paths.concept_index == Path("/tmp/idx/concept_index.json")
    assert paths.moc_map == Path("/tmp/idx/moc_map.json")
    assert paths.link_graph == Path("/tmp/idx/link_graph.json")
    assert paths.alias_map == Path("/tmp/idx/alias_map.json")


def test_load_concept_index(built_indexes):
    index = load_concept_index(built_indexes.concept_index)

    assert isinstance(index, dict)
    assert "oauth2-flow" in index
    entry = index["oauth2-flow"]
    assert entry["title"] == "OAuth2 Flow"
    assert "auth" in entry["tags"]


def test_load_moc_map(built_indexes):
    mocs = load_moc_map(built_indexes.moc_map)
    assert isinstance(mocs, dict)
    assert "authentication" in mocs
    assert "oauth2-flow" in mocs["authentication"]["children"]


def test_load_link_graph(built_indexes):
    graph = load_link_graph(built_indexes.link_graph)
    assert isinstance(graph, dict)
    # oauth2-flow has prerequisites in the example vault
    assert graph["oauth2-flow"]["prerequisites"] == ["http-basics", "encryption-fundamentals"]
    # Inverse: http-basics leads_to oauth2-flow
    assert "oauth2-flow" in graph["http-basics"]["leads_to"]


def test_load_alias_map(built_indexes):
    aliases = load_alias_map(built_indexes.alias_map)
    assert isinstance(aliases, dict)
    # Example vault has no aliases set
    assert aliases == {}


def test_load_concept_index_missing_file_raises(tmp_path: Path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_concept_index(tmp_path / "nope.json")
