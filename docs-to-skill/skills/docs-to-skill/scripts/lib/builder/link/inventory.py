"""Build a compact 'concept inventory' for the Link Agent.

Each entry is one concept reduced to its name, title, 1-sentence summary,
and tags — small enough for the agent to cluster hundreds of concepts at
once without exceeding context limits.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from matter_expert import ConceptPage


SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ConceptSummary:
    """Compact representation of a concept for clustering/linking."""
    name: str
    title: str
    summary: str
    tags: list[str]


def _first_sentence(body: str) -> str:
    """Return the first sentence of the body, stripping heading lines."""
    # Skip blank lines and heading lines at the top.
    lines = body.splitlines()
    while lines and (not lines[0].strip() or lines[0].lstrip().startswith("#")):
        lines.pop(0)
    if not lines:
        return ""
    # Reflow remaining lines until first sentence boundary.
    paragraph = " ".join(lines).strip()
    if not paragraph:
        return ""
    parts = SENTENCE_END.split(paragraph, maxsplit=1)
    return parts[0].strip()


def build_inventory(concepts_dir: Path) -> list[ConceptSummary]:
    """Build a sorted-by-name inventory of all concept pages under `concepts_dir`."""
    summaries: list[ConceptSummary] = []
    for path in sorted(concepts_dir.glob("*.md")):
        page = ConceptPage.read(path)
        summaries.append(ConceptSummary(
            name=page.name,
            title=page.frontmatter.title,
            summary=_first_sentence(page.body),
            tags=list(page.frontmatter.tags),
        ))
    return summaries
