"""YAML frontmatter parsing/writing for vault markdown files."""
from dataclasses import dataclass
from typing import Any

import frontmatter


@dataclass
class ParsedDocument:
    """A markdown document split into metadata (frontmatter) and body."""

    metadata: dict[str, Any]
    body: str


def parse_frontmatter(content: str) -> ParsedDocument:
    """Parse a markdown string into metadata + body."""
    post = frontmatter.loads(content)
    return ParsedDocument(metadata=dict(post.metadata), body=post.content)


def write_frontmatter(doc: ParsedDocument) -> str:
    """Serialize a parsed document back to a markdown string."""
    post = frontmatter.Post(content=doc.body, **doc.metadata)
    return frontmatter.dumps(post)
