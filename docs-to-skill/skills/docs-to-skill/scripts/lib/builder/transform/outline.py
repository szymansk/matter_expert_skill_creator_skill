"""Concept outline produced by the analyzer."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OutlineEntry:
    """One concept identified during source-document analysis."""
    concept_name: str           # filename-stem form: "oauth2-flow"
    title: str                  # display title: "OAuth2 Flow"
    source_sections: list[str]  # e.g. ["3.1", "3.2"]
    estimated_tokens: int

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OutlineEntry":
        return cls(
            concept_name=data["concept_name"],
            title=data["title"],
            source_sections=list(data.get("source_sections", [])),
            estimated_tokens=int(data["estimated_tokens"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "concept_name": self.concept_name,
            "title": self.title,
            "source_sections": list(self.source_sections),
            "estimated_tokens": self.estimated_tokens,
        }


@dataclass
class ConceptOutline:
    """List of identified concepts for one source document."""
    entries: list[OutlineEntry] = field(default_factory=list)

    def __iter__(self):
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConceptOutline":
        return cls(entries=[
            OutlineEntry.from_dict(e) for e in data.get("entries", [])
        ])

    def to_dict(self) -> dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}
