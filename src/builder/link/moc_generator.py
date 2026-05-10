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
        """Write one MOC per shared tag. Returns the list of written MOCPages."""
        mocs_dir.mkdir(parents=True, exist_ok=True)
        # Group concepts by tag.
        by_tag: dict[str, list[str]] = defaultdict(list)
        for s in inventory:
            for t in s.tags:
                by_tag[t].append(s.name)

        written: list[MOCPage] = []
        for tag in sorted(by_tag):
            children = sorted(by_tag[tag])
            if len(children) < 2:
                continue
            fm = MOCFrontmatter(
                title=tag.title(),
                children=children,
                parents=[],
                related_mocs=[],
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
