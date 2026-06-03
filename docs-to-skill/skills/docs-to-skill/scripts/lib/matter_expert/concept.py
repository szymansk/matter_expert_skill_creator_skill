"""Concept page domain model — the core unit of the vault."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from matter_expert.frontmatter import ParsedDocument, parse_frontmatter, write_frontmatter
from matter_expert.wikilinks import normalize_wikilink


@dataclass(frozen=True)
class Source:
    """A reference to a source document and the sections it backs."""

    file: str
    sections: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Source":
        return cls(
            file=data["file"],
            sections=list(data.get("sections", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"file": self.file, "sections": list(self.sections)}


@dataclass
class ConceptFrontmatter:
    """Structured frontmatter of a concept page.

    Mandatory fields: title, sources, tags, created.
    Typed link fields default to empty lists.
    Wikilink targets are normalized (bare names, no `[[...]]`).
    """

    title: str
    sources: list[Source]
    tags: list[str]
    created: date
    related: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    contrasts: list[str] = field(default_factory=list)
    refines: list[str] = field(default_factory=list)
    merged_from: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConceptFrontmatter":
        return cls(
            title=data["title"],
            sources=[Source.from_dict(s) for s in data["sources"]],
            tags=list(data["tags"]),
            created=data["created"],
            related=[normalize_wikilink(x) for x in data.get("related", [])],
            prerequisites=[normalize_wikilink(x) for x in data.get("prerequisites", [])],
            examples=[normalize_wikilink(x) for x in data.get("examples", [])],
            contrasts=[normalize_wikilink(x) for x in data.get("contrasts", [])],
            refines=[normalize_wikilink(x) for x in data.get("refines", [])],
            merged_from=list(data.get("merged_from", [])),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "sources": [s.to_dict() for s in self.sources],
            "tags": list(self.tags),
            "created": self.created,
            "related": list(self.related),
            "prerequisites": list(self.prerequisites),
            "examples": list(self.examples),
            "contrasts": list(self.contrasts),
            "refines": list(self.refines),
            "merged_from": list(self.merged_from),
        }


@dataclass
class ConceptPage:
    """A vault concept page: structured frontmatter + markdown body."""

    frontmatter: ConceptFrontmatter
    body: str
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem

    @classmethod
    def read(cls, path: Path) -> "ConceptPage":
        parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        return cls(
            frontmatter=ConceptFrontmatter.from_dict(parsed.metadata),
            body=parsed.body,
            path=path,
        )

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = ParsedDocument(
            metadata=self.frontmatter.to_dict(),
            body=self.body,
        )
        self.path.write_text(write_frontmatter(doc), encoding="utf-8")
