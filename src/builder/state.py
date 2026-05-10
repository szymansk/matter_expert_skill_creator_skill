"""Pipeline state types and on-disk JSON serialization.

The state lives at ~/.docs-to-skill/<run-id>/pipeline_state.json and is
the single source of truth for which phase/items have completed, what
they cost, and what failed. All serialization uses stdlib json + sort_keys
so commits and diffs are deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ItemState:
    """Status of a single work-item within a phase (e.g., one input PDF).

    status: "pending" | "in_progress" | "done" | "failed"
    metadata: arbitrary phase-specific info (e.g., {"method": "vision_fallback"})
    """
    status: str = "pending"
    completed_at: str | None = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ItemState":
        return cls(
            status=data.get("status", "pending"),
            completed_at=data.get("completed_at"),
            error=data.get("error"),
            metadata=dict(data.get("metadata", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "completed_at": self.completed_at,
            "error": self.error,
            "metadata": dict(self.metadata),
        }


@dataclass
class PhaseState:
    """Status of an entire pipeline phase.

    status: "pending" | "in_progress" | "completed" | "failed"
    items: per-item states keyed by stable item id
    """
    name: str
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    items: dict[str, ItemState] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PhaseState":
        return cls(
            name=data["name"],
            status=data.get("status", "pending"),
            started_at=data.get("started_at"),
            completed_at=data.get("completed_at"),
            items={
                k: ItemState.from_dict(v)
                for k, v in data.get("items", {}).items()
            },
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "items": {k: v.to_dict() for k, v in self.items.items()},
        }
