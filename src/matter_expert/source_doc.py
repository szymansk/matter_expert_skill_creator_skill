"""Source document page — original input converted to markdown."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Literal

from matter_expert.frontmatter import ParsedDocument, parse_frontmatter, write_frontmatter

ExtractionMethod = Literal["text", "vision_fallback", "hybrid"]


@dataclass
class SourceFrontmatter:
    """Frontmatter for a vault/sources/ page (the original document)."""

    title: str
    original_file: str
    original_format: str
    page_count: int
    extraction_method: ExtractionMethod
    language_detected: str
    ingested: date

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceFrontmatter":
        return cls(
            title=data["title"],
            original_file=data["original_file"],
            original_format=data["original_format"],
            page_count=int(data["page_count"]),
            extraction_method=data["extraction_method"],
            language_detected=data["language_detected"],
            ingested=data["ingested"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "original_file": self.original_file,
            "original_format": self.original_format,
            "page_count": self.page_count,
            "extraction_method": self.extraction_method,
            "language_detected": self.language_detected,
            "ingested": self.ingested,
        }


@dataclass
class SourcePage:
    """A vault/sources/ page."""

    frontmatter: SourceFrontmatter
    body: str
    path: Path

    @property
    def name(self) -> str:
        return self.path.stem

    @classmethod
    def read(cls, path: Path) -> "SourcePage":
        parsed = parse_frontmatter(path.read_text(encoding="utf-8"))
        return cls(
            frontmatter=SourceFrontmatter.from_dict(parsed.metadata),
            body=parsed.body,
            path=path,
        )

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc = ParsedDocument(metadata=self.frontmatter.to_dict(), body=self.body)
        self.path.write_text(write_frontmatter(doc), encoding="utf-8")
