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
