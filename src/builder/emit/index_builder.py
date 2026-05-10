"""Build the 4 JSON index files from the vault using matter_expert builders."""
from __future__ import annotations

from pathlib import Path

from matter_expert import (
    AliasMap, ConceptIndex, ConceptIndexEntry, ConceptPage,
    LinkGraph, MOCMap, MOCMapEntry, MOCPage, VaultPaths,
)


def build_indexes(vault: VaultPaths, index_dir: Path) -> None:
    """Generate concept_index, moc_map, link_graph, alias_map as JSON files."""
    index_dir.mkdir(parents=True, exist_ok=True)

    # Load concept pages.
    concept_pages: dict[str, ConceptPage] = {}
    if vault.concepts.exists():
        for path in sorted(vault.concepts.glob("*.md")):
            page = ConceptPage.read(path)
            concept_pages[page.name] = page

    # ConceptIndex: concept_name → ConceptIndexEntry
    def _summary(body: str) -> str:
        # First non-heading line, truncated to 120 chars.
        lines = body.splitlines()
        while lines and (not lines[0].strip()
                          or lines[0].lstrip().startswith("#")):
            lines.pop(0)
        return " ".join(lines).strip()[:120]

    concept_index = ConceptIndex({
        name: ConceptIndexEntry(
            path=f"concepts/{name}.md",
            title=page.frontmatter.title,
            summary=_summary(page.body),
            tags=list(page.frontmatter.tags),
            aliases=[],
            moc=[],
        )
        for name, page in concept_pages.items()
    })
    concept_index.write(index_dir / "concept_index.json")

    # MOCMap from vault/MOCs/.
    moc_pages: dict[str, MOCPage] = {}
    if vault.mocs.exists():
        for path in sorted(vault.mocs.glob("*.md")):
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

    # LinkGraph with inverse links materialized.
    link_graph = LinkGraph.build({
        name: page.frontmatter for name, page in concept_pages.items()
    })
    link_graph.write(index_dir / "link_graph.json")

    # AliasMap inverted from concept_index aliases.
    alias_map = AliasMap.build(concept_index)
    alias_map.write(index_dir / "alias_map.json")
