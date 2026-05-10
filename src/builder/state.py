"""Pipeline state types and on-disk JSON serialization.

The state lives at ~/.docs-to-skill/<run-id>/pipeline_state.json and is
the single source of truth for which phase/items have completed, what
they cost, and what failed. All serialization uses stdlib json + sort_keys
so commits and diffs are deterministic.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
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


@dataclass
class PipelineState:
    """The complete persistent state of a pipeline run.

    `phases` is initialized with one PhaseState per known pipeline phase
    so callers never need to pre-create them.
    """
    run_id: str
    input_dir: str
    url_list: list[str]
    started: str
    phases: dict[str, PhaseState] = field(default_factory=dict)
    cost_tracker: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Pre-populate phase states for the 5 known phases.
        from builder.phases import Phase
        if not self.phases:
            for phase in Phase:
                self.phases[phase.value] = PhaseState(name=phase.value)
        if not self.cost_tracker:
            self.cost_tracker = {
                "estimated_total_usd": 0.0,
                "actual_so_far_usd": 0.0,
                "per_phase": {},
            }

    @classmethod
    def read(cls, path: Path) -> "PipelineState":
        raw = json.loads(path.read_text(encoding="utf-8"))
        state = cls(
            run_id=raw["run_id"],
            input_dir=raw["input_dir"],
            url_list=list(raw.get("url_list", [])),
            started=raw["started"],
            phases={
                k: PhaseState.from_dict(v)
                for k, v in raw.get("phases", {}).items()
            },
            cost_tracker=dict(raw.get("cost_tracker", {})),
        )
        return state

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            "run_id": self.run_id,
            "input_dir": self.input_dir,
            "url_list": list(self.url_list),
            "started": self.started,
            "phases": {k: v.to_dict() for k, v in self.phases.items()},
            "cost_tracker": dict(self.cost_tracker),
        }
        path.write_text(
            json.dumps(serializable, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
