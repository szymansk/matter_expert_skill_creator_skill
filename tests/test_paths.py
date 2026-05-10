from pathlib import Path
from matter_expert.paths import VaultPaths


def test_vault_paths_construction():
    root = Path("/tmp/vault").resolve()
    paths = VaultPaths(root=root)

    assert paths.root == root
    assert paths.concepts == root / "concepts"
    assert paths.mocs == root / "MOCs"
    assert paths.sources == root / "sources"


def test_index_paths_construction():
    root = Path("/tmp/plugin").resolve()
    paths = VaultPaths(root=root)

    assert paths.index_dir == root.parent / "_index"
    assert paths.concept_index == paths.index_dir / "concept_index.json"
    assert paths.moc_map == paths.index_dir / "moc_map.json"
    assert paths.link_graph == paths.index_dir / "link_graph.json"
    assert paths.alias_map == paths.index_dir / "alias_map.json"


def test_concept_path_for_name():
    root = Path("/tmp/vault").resolve()
    paths = VaultPaths(root=root)

    assert paths.concept_for("oauth2-flow") == root / "concepts" / "oauth2-flow.md"


def test_moc_path_for_name():
    root = Path("/tmp/vault").resolve()
    paths = VaultPaths(root=root)

    assert paths.moc_for("authentication") == root / "MOCs" / "authentication.md"


def test_vault_paths_normalizes_relative_root_to_absolute():
    """A relative root is resolved to absolute so index_dir is well-defined."""
    paths = VaultPaths(root=Path("relative/path"))
    assert paths.root.is_absolute()
    assert paths.index_dir.is_absolute()


def test_vault_paths_passes_through_already_absolute_root():
    abs_path = Path("/tmp/some_absolute_vault").resolve()
    paths = VaultPaths(root=abs_path)
    assert paths.root == abs_path
