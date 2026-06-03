"""Generate MOC pages by grouping concepts on shared tags."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from builder.link.inventory import ConceptSummary
from matter_expert import MOCFrontmatter, MOCPage


class MOCGenerator:
    """Generates a MOC per tag (skipping singleton tags)."""

    def generate(
        self,
        inventory: list[ConceptSummary],
        mocs_dir: Path,
    ) -> list[MOCPage]:
        """Write one MOC per shared tag. Returns the list of written MOCPages.

        Horizontal cross-references (related_mocs) are set to any peer MOC
        that shares at least one concept child (i.e. a concept with multiple
        tags appears in both MOCs).
        """
        mocs_dir.mkdir(parents=True, exist_ok=True)
        # Group concepts by tag.
        by_tag: dict[str, list[str]] = defaultdict(list)
        for s in inventory:
            for t in s.tags:
                by_tag[t].append(s.name)

        # Only keep tags with 2+ concepts (same filter as before).
        moc_tags: dict[str, list[str]] = {
            tag: sorted(children)
            for tag, children in by_tag.items()
            if len(children) >= 2
        }

        # Build related_mocs: two MOCs are related when their child sets overlap.
        def _related(tag: str, children: list[str]) -> list[str]:
            child_set = set(children)
            return sorted(
                other_tag
                for other_tag, other_children in moc_tags.items()
                if other_tag != tag and child_set & set(other_children)
            )

        written: list[MOCPage] = []
        for tag in sorted(moc_tags):
            children = moc_tags[tag]
            related = _related(tag, children)
            fm = MOCFrontmatter(
                title=tag.title(),
                children=children,
                parents=[],
                related_mocs=related,
                created=datetime.now(timezone.utc).date(),
            )
            body = (
                f"# {tag.title()} MOC\n\n"
                f"## Concepts\n\n"
                + "\n".join(f"- [[{name}]]" for name in children)
                + "\n"
            )
            page = MOCPage(frontmatter=fm, body=body, path=mocs_dir / f"{tag}.md")
            page.write()
            written.append(page)
        return written
