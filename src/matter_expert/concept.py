"""Concept page domain model — the core unit of the vault."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


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
