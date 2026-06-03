"""YAML frontmatter parsing/writing for vault markdown files.

This module uses the vendored pure-Python YAML implementation (shipped under
``scripts/lib/yaml/``) rather than the third-party ``python-frontmatter`` package.
That keeps the whole plugin dependency-free: it works immediately after a
``/plugin marketplace add`` with zero pip installs. The public API
(``ParsedDocument``, ``parse_frontmatter``, ``write_frontmatter``) is unchanged,
so consumers (concept.py / source_doc.py / moc.py) need no edits.
"""
from dataclasses import dataclass
from typing import Any

import yaml

# A frontmatter block is delimited by a line containing exactly these three
# dashes. We match the opening at the very start of the document and the closing
# as the first subsequent line that is exactly the delimiter.
_DELIM = "---"


@dataclass
class ParsedDocument:
    """A markdown document split into metadata (frontmatter) and body."""

    metadata: dict[str, Any]
    body: str


def parse_frontmatter(content: str) -> ParsedDocument:
    """Parse a markdown string into metadata + body.

    A leading ``---`` opens a YAML frontmatter block that runs up to the next
    line that is exactly ``---``. If there is no opening delimiter (or no closing
    one), the entire string is treated as the body with empty metadata — this
    mirrors how the stdlib-only runtime strips frontmatter, so the two stay
    consistent.
    """
    if not content.startswith(_DELIM):
        return ParsedDocument(metadata={}, body=content)

    rest = content[len(_DELIM):]
    closing = rest.find("\n" + _DELIM)
    if closing == -1:
        # Malformed (no closing delimiter): treat the whole thing as body.
        return ParsedDocument(metadata={}, body=content)

    fm_text = rest[:closing]
    body = rest[closing + len("\n" + _DELIM):].lstrip("\n")
    metadata = yaml.safe_load(fm_text) or {}
    return ParsedDocument(metadata=metadata, body=body)


def write_frontmatter(doc: ParsedDocument) -> str:
    """Serialize a parsed document back to a markdown string.

    ``sort_keys=False`` preserves the author's key order (e.g. ``sources`` lists
    of ``{file, sections}`` dicts), which the roundtrip tests rely on.
    ``datetime.date`` values serialize to ISO ``YYYY-MM-DD`` and parse back to a
    ``date``, so date fields like ``created`` roundtrip cleanly.
    """
    dumped = yaml.safe_dump(
        doc.metadata,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).rstrip("\n")
    return f"{_DELIM}\n{dumped}\n{_DELIM}\n\n{doc.body}"
