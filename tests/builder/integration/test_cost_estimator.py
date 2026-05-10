from pathlib import Path

from builder.integration.cost_estimator import (
    CostEstimate, PhaseEstimate, estimate_build_cost,
)
from builder.phases import Phase


def test_phase_estimate_construction():
    e = PhaseEstimate(phase=Phase.INGEST, low_usd=0.0, high_usd=1.20)
    assert e.low_usd == 0.0
    assert e.high_usd == 1.20


def test_cost_estimate_total():
    estimate = CostEstimate(
        per_phase=[
            PhaseEstimate(Phase.INGEST, 0.0, 1.20),
            PhaseEstimate(Phase.TRANSFORM, 4.50, 5.80),
        ],
        buffer_pct=0.20,
    )
    # low = 0.0 + 4.50 = 4.50; high = 1.20 + 5.80 = 7.00
    # buffer (high) = 0.20 * 7.00 = 1.40 → totals 8.40
    assert estimate.total_low_usd == 4.50 * 1.20  # +20% buffer
    assert estimate.total_high_usd == 7.00 * 1.20


def test_estimate_from_input_dir(tmp_path: Path):
    """A directory with N text files produces non-zero estimates for all phases."""
    (tmp_path / "a.md").write_text("# X\n" + "word " * 500)
    (tmp_path / "b.txt").write_text("plain text content " * 200)

    estimate = estimate_build_cost(input_dir=tmp_path, url_list=[])
    assert len(estimate.per_phase) == 5
    # Ingest is cheap (or zero) for text-only inputs.
    ingest = next(p for p in estimate.per_phase if p.phase == Phase.INGEST)
    assert ingest.low_usd == 0.0
    # Transform/Link/Emit should have positive estimates.
    transform = next(p for p in estimate.per_phase if p.phase == Phase.TRANSFORM)
    assert transform.high_usd > 0


def test_estimate_includes_urls(tmp_path: Path):
    """URL list adds to Ingest estimate."""
    estimate_no_urls = estimate_build_cost(input_dir=tmp_path, url_list=[])
    estimate_with_urls = estimate_build_cost(
        input_dir=tmp_path,
        url_list=["https://example.com/a", "https://example.com/b"],
    )
    # URLs touch Ingest (vision fallback heuristic for HTML pages).
    no_ingest = next(p for p in estimate_no_urls.per_phase if p.phase == Phase.INGEST)
    with_ingest = next(p for p in estimate_with_urls.per_phase if p.phase == Phase.INGEST)
    assert with_ingest.high_usd > no_ingest.high_usd


def test_estimate_formatted_breakdown():
    """`format()` produces a human breakdown matching design spec §7.1."""
    estimate = CostEstimate(
        per_phase=[
            PhaseEstimate(Phase.INGEST, 0.0, 1.20),
            PhaseEstimate(Phase.TRANSFORM, 4.50, 5.80),
            PhaseEstimate(Phase.LINK, 2.10, 2.10),
            PhaseEstimate(Phase.QA, 0.80, 0.80),
            PhaseEstimate(Phase.EMIT, 0.40, 0.40),
        ],
        buffer_pct=0.20,
    )
    output = estimate.format()
    assert "Ingest" in output
    assert "Buffer" in output
    assert "Total" in output
    assert "20%" in output
