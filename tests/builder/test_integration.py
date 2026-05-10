"""End-to-end integration test simulating a full pipeline run.

No actual phase logic is invoked — just the framework's state transitions.
This test verifies that all the pieces compose correctly into a realistic
lifecycle: create → run phases → record items → record costs → resume → replay.
"""
from pathlib import Path

from builder.cost_tracker import (
    MODEL_PRICES_USD_PER_MILLION,
    TokenUsage,
    estimate_cost,
)
from builder.failures import FailureClass, PipelineError, with_retry
from builder.phases import (
    DEFAULT_CONFIGS,
    Effort,
    Model,
    Phase,
    config_for_phase,
)
from builder.pipeline import Pipeline


def test_full_pipeline_lifecycle(run_dir: Path):
    """Simulate a complete pipeline run with all framework features."""
    # 1. Create a fresh run with an estimated budget.
    pipeline = Pipeline.create(
        run_id="2026-05-10-integration-test",
        input_dir=Path("/tmp/fake_inputs"),
        url_list=["https://example.com/spec"],
        run_dir=run_dir,
    )
    pipeline.set_estimated_total(11.80)
    assert pipeline.state.cost_tracker["estimated_total_usd"] == 11.80

    # 2. Run Ingest: process 3 documents.
    pipeline.mark_phase_started(Phase.INGEST)
    pipeline.record_item(Phase.INGEST, "doc_001.pdf", status="done", method="text")
    pipeline.record_item(Phase.INGEST, "doc_002.pdf", status="done", method="vision_fallback")
    pipeline.record_item(Phase.INGEST, "doc_003.pdf", status="failed",
                         error="unreadable")
    pipeline.record_cost(Phase.INGEST, 0.50)
    pipeline.mark_phase_completed(Phase.INGEST)

    assert pipeline.is_phase_complete(Phase.INGEST)
    assert pipeline.next_pending_phase() == Phase.TRANSFORM

    # 3. Run Transform with a configured model + estimated cost.
    config = config_for_phase(Phase.TRANSFORM, DEFAULT_CONFIGS)
    assert config.model == Model.HAIKU
    assert config.effort == Effort.MEDIUM

    pipeline.mark_phase_started(Phase.TRANSFORM)
    usage = TokenUsage(input_tokens=2_000_000, output_tokens=500_000)
    cost = estimate_cost(config.model, usage)
    pipeline.record_cost(Phase.TRANSFORM, cost)
    pipeline.mark_phase_completed(Phase.TRANSFORM)

    expected_transform_cost = (
        2.0 * MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["input"]
        + 0.5 * MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["output"]
    )
    assert (
        pipeline.state.cost_tracker["per_phase"]["transform"]
        == expected_transform_cost
    )

    # 4. Resume from disk in a separate Pipeline instance — state is preserved.
    resumed = Pipeline.resume(run_dir)
    assert resumed.state.phases["ingest"].status == "completed"
    assert resumed.state.phases["transform"].status == "completed"
    assert len(resumed.state.phases["ingest"].items) == 3
    assert resumed.state.phases["ingest"].items["doc_003.pdf"].status == "failed"

    # 5. Replay from Link onwards.
    resumed.mark_phase_started(Phase.LINK)
    resumed.mark_phase_completed(Phase.LINK)
    resumed.record_cost(Phase.LINK, 1.80)
    cost_before_replay = resumed.state.cost_tracker["actual_so_far_usd"]

    resumed.replay_from(Phase.LINK)

    assert resumed.state.phases["link"].status == "pending"
    assert "link" not in resumed.state.cost_tracker["per_phase"]
    assert resumed.state.cost_tracker["actual_so_far_usd"] < cost_before_replay
    assert resumed.next_pending_phase() == Phase.LINK


def test_retry_decorator_with_real_pipeline_error():
    """A function that raises a TRANSIENT PipelineError gets retried."""
    attempts: list[int] = []

    @with_retry(max_attempts=3, backoff_base=0.0)
    def flaky_agent_call() -> str:
        attempts.append(1)
        if len(attempts) < 2:
            raise PipelineError("rate limit", FailureClass.TRANSIENT)
        return "agent_response"

    assert flaky_agent_call() == "agent_response"
    assert len(attempts) == 2
