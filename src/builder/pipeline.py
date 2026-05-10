"""The Pipeline orchestrator class.

Owns the `pipeline_state.json` file under a run directory. Provides
methods to create a fresh run, resume an existing one, replay a phase,
and record progress (phase status, item status, cost).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder.phases import Phase
from builder.state import PipelineState


STATE_FILE_NAME = "pipeline_state.json"


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Pipeline:
    """Orchestrates a single pipeline run, persisting state to disk."""

    def __init__(self, run_dir: Path, state: PipelineState) -> None:
        self._run_dir = run_dir
        self._state = state
        self._state_path = run_dir / STATE_FILE_NAME

    @property
    def state(self) -> PipelineState:
        return self._state

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    def _save(self) -> None:
        self._state.write(self._state_path)

    @classmethod
    def create(
        cls,
        run_id: str,
        input_dir: Path,
        url_list: list[str],
        run_dir: Path,
    ) -> "Pipeline":
        """Create a fresh pipeline run.

        Raises:
            FileExistsError: if `run_dir` already contains a pipeline_state.json.
        """
        state_path = run_dir / STATE_FILE_NAME
        if state_path.exists():
            raise FileExistsError(
                f"pipeline_state.json already exists at {run_dir} — use resume()"
            )
        state = PipelineState(
            run_id=run_id,
            input_dir=str(input_dir),
            url_list=list(url_list),
            started=_utc_iso_now(),
        )
        pipeline = cls(run_dir=run_dir, state=state)
        pipeline._save()
        return pipeline

    @classmethod
    def resume(cls, run_dir: Path) -> "Pipeline":
        """Load an existing pipeline run from `run_dir/pipeline_state.json`.

        Raises:
            FileNotFoundError: if no state file is found.
        """
        state_path = run_dir / STATE_FILE_NAME
        if not state_path.exists():
            raise FileNotFoundError(
                f"no pipeline_state.json at {run_dir} — use create() instead"
            )
        state = PipelineState.read(state_path)
        return cls(run_dir=run_dir, state=state)

    def mark_phase_started(self, phase: Phase) -> None:
        """Set phase status to in_progress and record start timestamp."""
        ps = self._state.phases[phase.value]
        ps.status = "in_progress"
        ps.started_at = _utc_iso_now()
        self._save()

    def mark_phase_completed(self, phase: Phase) -> None:
        """Set phase status to completed and record completion timestamp."""
        ps = self._state.phases[phase.value]
        ps.status = "completed"
        ps.completed_at = _utc_iso_now()
        self._save()

    def mark_phase_failed(self, phase: Phase, error: str) -> None:
        """Set phase status to failed."""
        from builder.state import ItemState
        ps = self._state.phases[phase.value]
        ps.status = "failed"
        ps.completed_at = _utc_iso_now()
        ps.items["_phase"] = ItemState(
            status="failed",
            completed_at=ps.completed_at,
            error=error,
        )
        self._save()

    def record_item(
        self,
        phase: Phase,
        item_id: str,
        status: str,
        error: str | None = None,
        **metadata: Any,
    ) -> None:
        """Record or update the state of a single item within a phase."""
        from builder.state import ItemState
        ps = self._state.phases[phase.value]
        existing = ps.items.get(item_id, ItemState())
        existing.status = status
        if status in ("done", "failed"):
            existing.completed_at = _utc_iso_now()
        if error is not None:
            existing.error = error
        existing.metadata.update(metadata)
        ps.items[item_id] = existing
        self._save()

    def record_cost(self, phase: Phase, usd: float) -> None:
        """Add an incremental cost to the phase's total and the global running total."""
        per_phase = self._state.cost_tracker["per_phase"]
        per_phase[phase.value] = round(per_phase.get(phase.value, 0.0) + usd, 10)
        self._state.cost_tracker["actual_so_far_usd"] = round(
            self._state.cost_tracker.get("actual_so_far_usd", 0.0) + usd, 10
        )
        self._save()

    def set_estimated_total(self, usd: float) -> None:
        """Set the upfront cost estimate (called once after computing the breakdown)."""
        self._state.cost_tracker["estimated_total_usd"] = usd
        self._save()

    def is_phase_complete(self, phase: Phase) -> bool:
        """Return True iff the phase's status is `completed`."""
        return self._state.phases[phase.value].status == "completed"

    def next_pending_phase(self) -> Phase | None:
        """Return the first phase whose status is not `completed`, or None if all are."""
        for phase in Phase:
            if not self.is_phase_complete(phase):
                return phase
        return None

    def replay_from(self, phase: Phase) -> None:
        """Reset the given phase and all later phases to pending.

        Clears their items and per-phase costs. Earlier phases are
        untouched. The aggregate `actual_so_far_usd` is recomputed
        from the surviving per-phase totals.
        """
        from builder.state import PhaseState
        phases_in_order = list(Phase)
        target_index = phases_in_order.index(phase)

        for later in phases_in_order[target_index:]:
            name = later.value
            self._state.phases[name] = PhaseState(name=name)
            self._state.cost_tracker["per_phase"].pop(name, None)

        self._state.cost_tracker["actual_so_far_usd"] = round(
            sum(self._state.cost_tracker["per_phase"].values()), 10
        )
        self._save()
