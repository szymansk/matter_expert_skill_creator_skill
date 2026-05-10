from pathlib import Path

import pytest

from builder.pipeline import Pipeline
from builder.state import PipelineState


def test_create_writes_initial_state_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=["https://example.com/x"],
        run_dir=run_dir,
    )
    assert (run_dir / "pipeline_state.json").exists()


def test_create_sets_run_id_and_input_dir(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=[],
        run_dir=run_dir,
    )
    assert pipeline.state.run_id == "2026-05-10-test"
    assert pipeline.state.input_dir == "/tmp/inputs"


def test_create_records_started_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x",
        input_dir=Path("/tmp"),
        url_list=[],
        run_dir=run_dir,
    )
    # ISO 8601 UTC format
    assert pipeline.state.started.endswith("Z")
    assert "T" in pipeline.state.started


def test_create_initializes_all_5_phases_as_pending(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x",
        input_dir=Path("/tmp"),
        url_list=[],
        run_dir=run_dir,
    )
    for phase_name in ["ingest", "transform", "link", "qa", "emit"]:
        assert pipeline.state.phases[phase_name].status == "pending"


def test_create_fails_if_run_dir_already_has_state(run_dir: Path):
    Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    with pytest.raises(FileExistsError):
        Pipeline.create(
            run_id="y", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
        )


def test_resume_loads_existing_state(run_dir: Path):
    original = Pipeline.create(
        run_id="2026-05-10-test",
        input_dir=Path("/tmp/inputs"),
        url_list=["https://example.com/x"],
        run_dir=run_dir,
    )

    resumed = Pipeline.resume(run_dir)
    assert resumed.state.run_id == "2026-05-10-test"
    assert resumed.state.input_dir == "/tmp/inputs"
    assert resumed.state.url_list == ["https://example.com/x"]


def test_resume_fails_if_state_missing(run_dir: Path):
    with pytest.raises(FileNotFoundError):
        Pipeline.resume(run_dir)


def test_resume_preserves_phase_progress(run_dir: Path):
    """If the state file shows ingest completed, resume reflects that."""
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.state.phases["ingest"].status = "completed"
    pipeline._save()

    resumed = Pipeline.resume(run_dir)
    assert resumed.state.phases["ingest"].status == "completed"
    assert resumed.state.phases["transform"].status == "pending"


from builder.phases import Phase


def test_mark_phase_started_sets_status_and_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "in_progress"
    assert phase_state.started_at is not None


def test_mark_phase_completed_sets_status_and_timestamp(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "completed"
    assert phase_state.completed_at is not None


def test_mark_phase_failed_records_error(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_failed(Phase.INGEST, error="model unavailable")

    phase_state = pipeline.state.phases["ingest"]
    assert phase_state.status == "failed"


def test_mark_phase_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.phases["ingest"].status == "in_progress"


def test_record_item_creates_new_item(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(
        Phase.INGEST,
        item_id="doc_001.pdf",
        status="done",
        method="text",
        page_count=42,
    )

    item = pipeline.state.phases["ingest"].items["doc_001.pdf"]
    assert item.status == "done"
    assert item.completed_at is not None
    assert item.metadata["method"] == "text"
    assert item.metadata["page_count"] == 42


def test_record_item_updates_existing_item(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="in_progress")
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done")

    item = pipeline.state.phases["ingest"].items["doc_001.pdf"]
    assert item.status == "done"


def test_record_item_failed_captures_error(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(
        Phase.INGEST,
        "doc_003.pdf",
        status="failed",
        error="extraction failed: no text recoverable",
    )

    item = pipeline.state.phases["ingest"].items["doc_003.pdf"]
    assert item.status == "failed"
    assert "extraction failed" in (item.error or "")


def test_record_cost_adds_to_phase_total(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.42)
    pipeline.record_cost(Phase.INGEST, 0.18)

    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.60
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 0.60


def test_record_cost_separate_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.40)
    pipeline.record_cost(Phase.TRANSFORM, 4.20)

    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.40
    assert pipeline.state.cost_tracker["per_phase"]["transform"] == 4.20
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 4.60


def test_record_cost_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.LINK, 1.80)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.cost_tracker["per_phase"]["link"] == 1.80


def test_set_estimated_total_persists(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.set_estimated_total(11.80)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.cost_tracker["estimated_total_usd"] == 11.80


def test_is_phase_complete_initially_false(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        assert pipeline.is_phase_complete(phase) is False


def test_is_phase_complete_after_marking(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    assert pipeline.is_phase_complete(Phase.INGEST) is True
    assert pipeline.is_phase_complete(Phase.TRANSFORM) is False


def test_next_pending_phase_first_run(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    assert pipeline.next_pending_phase() == Phase.INGEST


def test_next_pending_phase_skips_completed(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    pipeline.mark_phase_started(Phase.TRANSFORM)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    assert pipeline.next_pending_phase() == Phase.LINK


def test_next_pending_phase_returns_none_when_all_done(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        pipeline.mark_phase_started(phase)
        pipeline.mark_phase_completed(phase)

    assert pipeline.next_pending_phase() is None


def test_replay_from_resets_target_phase(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)
    pipeline.mark_phase_started(Phase.TRANSFORM)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    pipeline.replay_from(Phase.TRANSFORM)

    assert pipeline.state.phases["transform"].status == "pending"
    assert pipeline.state.phases["transform"].started_at is None
    assert pipeline.state.phases["transform"].completed_at is None


def test_replay_from_resets_all_later_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    for phase in Phase:
        pipeline.mark_phase_started(phase)
        pipeline.mark_phase_completed(phase)

    pipeline.replay_from(Phase.LINK)

    assert pipeline.state.phases["link"].status == "pending"
    assert pipeline.state.phases["qa"].status == "pending"
    assert pipeline.state.phases["emit"].status == "pending"
    assert pipeline.state.phases["ingest"].status == "completed"
    assert pipeline.state.phases["transform"].status == "completed"


def test_replay_from_clears_items_in_reset_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_item(Phase.LINK, "concept-a", status="done")
    pipeline.record_item(Phase.LINK, "concept-b", status="done")

    pipeline.replay_from(Phase.LINK)

    assert pipeline.state.phases["link"].items == {}


def test_replay_from_clears_costs_for_reset_phases(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.record_cost(Phase.INGEST, 0.40)
    pipeline.record_cost(Phase.TRANSFORM, 4.20)
    pipeline.record_cost(Phase.LINK, 1.80)

    pipeline.replay_from(Phase.LINK)

    assert "link" not in pipeline.state.cost_tracker["per_phase"]
    assert pipeline.state.cost_tracker["per_phase"]["ingest"] == 0.40
    assert pipeline.state.cost_tracker["per_phase"]["transform"] == 4.20
    assert pipeline.state.cost_tracker["actual_so_far_usd"] == 4.60


def test_replay_from_persists_to_disk(run_dir: Path):
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.mark_phase_completed(Phase.INGEST)

    pipeline.replay_from(Phase.INGEST)

    reloaded = Pipeline.resume(run_dir)
    assert reloaded.state.phases["ingest"].status == "pending"
