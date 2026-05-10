from builder.state import ItemState, PhaseState


def test_item_state_default_pending():
    item = ItemState()
    assert item.status == "pending"
    assert item.completed_at is None
    assert item.error is None
    assert item.metadata == {}


def test_item_state_to_dict_round_trip():
    item = ItemState(
        status="done",
        completed_at="2026-05-10T10:00:00Z",
        error=None,
        metadata={"method": "text", "extracted_chars": 12000},
    )
    assert ItemState.from_dict(item.to_dict()) == item


def test_phase_state_default_pending():
    phase = PhaseState(name="ingest")
    assert phase.name == "ingest"
    assert phase.status == "pending"
    assert phase.started_at is None
    assert phase.completed_at is None
    assert phase.error is None
    assert phase.items == {}


def test_phase_state_to_dict_round_trip():
    phase = PhaseState(
        name="transform",
        status="in_progress",
        started_at="2026-05-10T10:00:00Z",
        completed_at=None,
        error=None,
        items={
            "doc_001.pdf": ItemState(status="done", completed_at="2026-05-10T10:30:00Z"),
            "doc_002.pdf": ItemState(status="in_progress"),
        },
    )
    assert PhaseState.from_dict(phase.to_dict()) == phase


def test_phase_state_to_dict_round_trip_with_error():
    phase = PhaseState(
        name="ingest",
        status="failed",
        started_at="2026-05-10T10:00:00Z",
        completed_at="2026-05-10T10:01:00Z",
        error="model unavailable",
        items={},
    )
    assert PhaseState.from_dict(phase.to_dict()) == phase


def test_phase_state_from_dict_accepts_missing_optional_fields():
    """Older state files may omit fields; from_dict must tolerate that."""
    minimal = {"name": "qa", "status": "pending"}
    phase = PhaseState.from_dict(minimal)
    assert phase.name == "qa"
    assert phase.status == "pending"
    assert phase.items == {}


import json
from pathlib import Path

from builder.state import PipelineState


def test_pipeline_state_default_initialization():
    state = PipelineState(
        run_id="2026-05-10-test",
        input_dir="/tmp/inputs",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    # All 5 phase states should be pre-populated.
    assert set(state.phases.keys()) == {
        "ingest", "transform", "link", "qa", "emit"
    }
    for phase_state in state.phases.values():
        assert phase_state.status == "pending"
    assert state.cost_tracker == {
        "estimated_total_usd": 0.0,
        "actual_so_far_usd": 0.0,
        "per_phase": {},
    }


def test_pipeline_state_round_trip_through_disk(tmp_path: Path):
    state = PipelineState(
        run_id="2026-05-10-test",
        input_dir="/tmp/inputs",
        url_list=["https://example.com/spec"],
        started="2026-05-10T10:00:00Z",
    )
    state.phases["ingest"].status = "completed"
    state.cost_tracker["actual_so_far_usd"] = 0.42
    state.cost_tracker["per_phase"]["ingest"] = 0.42

    file = tmp_path / "pipeline_state.json"
    state.write(file)

    reloaded = PipelineState.read(file)
    assert reloaded == state


def test_pipeline_state_write_creates_parent_dirs(tmp_path: Path):
    state = PipelineState(
        run_id="x",
        input_dir="/tmp",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    nested = tmp_path / "deep" / "nested" / "pipeline_state.json"
    state.write(nested)
    assert nested.exists()


def test_pipeline_state_disk_is_json_with_sorted_keys(tmp_path: Path):
    state = PipelineState(
        run_id="x",
        input_dir="/tmp",
        url_list=[],
        started="2026-05-10T10:00:00Z",
    )
    file = tmp_path / "ps.json"
    state.write(file)
    raw = json.loads(file.read_text(encoding="utf-8"))
    assert raw["run_id"] == "x"
    assert "phases" in raw
