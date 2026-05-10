"""Vault directory schema — knows where things live."""
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VaultPaths:
    """Resolves all standard paths inside (and adjacent to) a vault.

    Vault directory layout:
        <root>/
            concepts/
            MOCs/
            sources/

    Index files live as siblings of the vault root:
        <root>/../
            _index/
                concept_index.json
                moc_map.json
                link_graph.json
                alias_map.json
    """

    root: Path

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", self.root.resolve())

    @property
    def concepts(self) -> Path:
        return self.root / "concepts"

    @property
    def mocs(self) -> Path:
        return self.root / "MOCs"

    @property
    def sources(self) -> Path:
        return self.root / "sources"

    @property
    def index_dir(self) -> Path:
        return self.root.parent / "_index"

    @property
    def concept_index(self) -> Path:
        return self.index_dir / "concept_index.json"

    @property
    def moc_map(self) -> Path:
        return self.index_dir / "moc_map.json"

    @property
    def link_graph(self) -> Path:
        return self.index_dir / "link_graph.json"

    @property
    def alias_map(self) -> Path:
        return self.index_dir / "alias_map.json"

    def concept_for(self, name: str) -> Path:
        return self.concepts / f"{name}.md"

    def moc_for(self, name: str) -> Path:
        return self.mocs / f"{name}.md"

    def source_for(self, name: str) -> Path:
        return self.sources / f"{name}.md"
