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
    metadata, body = frontmatter.parse(content)
    return ParsedDocument(metadata=metadata, body=body)


def write_frontmatter(doc: ParsedDocument) -> str:
    """Serialize a parsed document back to a markdown string."""
    post = frontmatter.Post(content=doc.body)
    post.metadata = doc.metadata
    return frontmatter.dumps(post)
