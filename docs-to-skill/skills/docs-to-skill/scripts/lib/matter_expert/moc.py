"""MOC (Map of Content) page domain model."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from matter_expert.frontmatter import ParsedDocument, parse_frontmatter, write_frontmatter
from matter_expert.wikilinks import normalize_wikilink


@dataclass
class MOCFrontmatter:
    """Frontmatter for a Map-of-Content page.

    children: vault concepts directly under this MOC
    parents: parent MOCs (this MOC is one level deeper)
    related_mocs: peer MOCs covering related areas
    """

    title: str
    children: list[str]
    parents: list[str]
    related_mocs: list[str]
    created: date

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MOCFrontmatter":
        return cls(
            title=data["title"],
            children=[normalize_wikilink(x) for x in data.get("children", [])],
            parents=[normalize_wikilink(x) for x in data.get("parents", [])],
            related_mocs=[normalize_wikilink(x) for x in data.get("related_mocs", [])],
            created=data["created"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "children": list(self.children),
            "parents": list(self.parents),
            "related_mocs": list(self.related_mocs),
            "created": self.created,
        }


@dataclass
class MOCPage:
    """A vault MOC page."""

    frontmatter: MOCFrontmatter
    body: str
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem

    @classmethod
    def read(cls, path: Path) -> "MOCPage":
        parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        return cls(
            frontmatter=MOCFrontmatter.from_dict(parsed.metadata),
            body=parsed.body,
            path=path,
        )

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = ParsedDocument(metadata=self.frontmatter.to_dict(), body=self.body)
        self.path.write_text(write_frontmatter(doc), encoding="utf-8")
