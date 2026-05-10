"""Pre-build cost estimation per design spec §7.1."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from builder.cost_tracker import (
    MODEL_PRICES_USD_PER_MILLION, TokenUsage, estimate_cost,
)
from builder.phases import Model, Phase


# Tunable per-phase multipliers (rough heuristics).
TRANSLATION_TOKENS_PER_CHAR = 1.0  # 1 token per source char post-trans
LINK_TOKENS_PER_CONCEPT = 600      # rough per-concept link prompt size
QA_TOKENS_PER_SAMPLE = 800
EMIT_FIXED_OUTPUT_TOKENS = 1000

VISION_FALLBACK_FRACTION_LOW = 0.0
VISION_FALLBACK_FRACTION_HIGH = 0.30
URL_TOKENS_PER_PAGE = 2000

CONCEPTS_PER_SOURCE_LOW = 3
CONCEPTS_PER_SOURCE_HIGH = 10


@dataclass(frozen=True)
class PhaseEstimate:
    phase: Phase
    low_usd: float
    high_usd: float


@dataclass(frozen=True)
class CostEstimate:
    per_phase: list[PhaseEstimate]
    buffer_pct: float

    @property
    def subtotal_low_usd(self) -> float:
        return sum(p.low_usd for p in self.per_phase)

    @property
    def subtotal_high_usd(self) -> float:
        return sum(p.high_usd for p in self.per_phase)

    @property
    def total_low_usd(self) -> float:
        return self.subtotal_low_usd * (1 + self.buffer_pct)

    @property
    def total_high_usd(self) -> float:
        return self.subtotal_high_usd * (1 + self.buffer_pct)

    def format(self) -> str:
        lines = ["Estimated costs:"]
        for est in self.per_phase:
            label = est.phase.value.title()
            if est.low_usd == est.high_usd:
                lines.append(f"  {label:<10} ${est.high_usd:>6.2f}")
            else:
                lines.append(
                    f"  {label:<10} ${est.low_usd:>6.2f} - ${est.high_usd:>6.2f}"
                )
        buffer_low = self.subtotal_low_usd * self.buffer_pct
        buffer_high = self.subtotal_high_usd * self.buffer_pct
        lines.append(
            f"  {'Buffer':<10} ${buffer_low:>6.2f} - ${buffer_high:>6.2f} "
            f"  ({int(self.buffer_pct * 100)}%)"
        )
        lines.append(f"  {'─' * 17}")
        lines.append(
            f"  {'Total':<10} ${self.total_low_usd:>6.2f} - ${self.total_high_usd:>6.2f}"
        )
        return "\n".join(lines)


def _file_size_chars(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, UnicodeDecodeError):
        return path.stat().st_size  # rough byte fallback


def estimate_build_cost(
    input_dir: Path,
    url_list: list[str],
    buffer_pct: float = 0.20,
) -> CostEstimate:
    """Estimate cost-per-phase for an upcoming build."""
    # Total input character count.
    total_chars = 0
    file_count = 0
    pdf_count = 0
    for path in input_dir.glob("*") if input_dir.exists() else []:
        if not path.is_file():
            continue
        file_count += 1
        total_chars += _file_size_chars(path)
        if path.suffix.lower() == ".pdf":
            pdf_count += 1

    # Ingest cost: text-only files are free. PDFs MAY require vision (Sonnet).
    vision_pages_low = int(pdf_count * VISION_FALLBACK_FRACTION_LOW)
    vision_pages_high = int(pdf_count * VISION_FALLBACK_FRACTION_HIGH)
    vision_cost_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=vision_pages_low * 1500,
                    output_tokens=vision_pages_low * 500),
    )
    vision_cost_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=vision_pages_high * 1500,
                    output_tokens=vision_pages_high * 500),
    )
    # URL fetch + parse: Ingest doesn't call LLM, but vision can be triggered
    # by URL pages with little body. Cost is essentially 0 for the URL-only path.
    url_cost = 0.0  # urllib + html parser, no LLM at ingest
    ingest = PhaseEstimate(
        Phase.INGEST,
        low_usd=round(vision_cost_low + url_cost, 4),
        high_usd=round(vision_cost_high + url_cost + 0.05 * len(url_list), 4),
    )

    # Transform cost: input chars → input tokens → Haiku translation + per-concept extract
    input_tokens = total_chars  # 1 token per char post-trans approximation
    estimated_concepts_low = file_count * CONCEPTS_PER_SOURCE_LOW
    estimated_concepts_high = file_count * CONCEPTS_PER_SOURCE_HIGH
    transform_low = estimate_cost(
        Model.HAIKU,
        TokenUsage(input_tokens=input_tokens * estimated_concepts_low // file_count
                    if file_count else 0,
                    output_tokens=estimated_concepts_low * 1500),
    )
    transform_high = estimate_cost(
        Model.HAIKU,
        TokenUsage(input_tokens=input_tokens * estimated_concepts_high // max(file_count, 1),
                    output_tokens=estimated_concepts_high * 1500),
    )
    transform = PhaseEstimate(
        Phase.TRANSFORM,
        low_usd=round(transform_low, 4),
        high_usd=round(transform_high, 4),
    )

    # Link cost: Sonnet, one prompt per concept (link assignment) + one cluster pass
    link_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=estimated_concepts_low * LINK_TOKENS_PER_CONCEPT,
                    output_tokens=estimated_concepts_low * 200),
    )
    link_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=estimated_concepts_high * LINK_TOKENS_PER_CONCEPT,
                    output_tokens=estimated_concepts_high * 200),
    )
    link = PhaseEstimate(
        Phase.LINK,
        low_usd=round(link_low, 4),
        high_usd=round(link_high, 4),
    )

    # QA cost: ~30% of concepts sampled across all LLM validators (Sonnet)
    qa_samples_low = int(estimated_concepts_low * 0.30)
    qa_samples_high = int(estimated_concepts_high * 0.30)
    qa_low = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=qa_samples_low * QA_TOKENS_PER_SAMPLE,
                    output_tokens=qa_samples_low * 100),
    )
    qa_high = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=qa_samples_high * QA_TOKENS_PER_SAMPLE,
                    output_tokens=qa_samples_high * 100),
    )
    qa = PhaseEstimate(
        Phase.QA,
        low_usd=round(qa_low, 4),
        high_usd=round(qa_high, 4),
    )

    # Emit cost: one Sonnet call for the SKILL.md trigger description
    emit_cost = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=2000, output_tokens=EMIT_FIXED_OUTPUT_TOKENS),
    )
    emit = PhaseEstimate(
        Phase.EMIT,
        low_usd=round(emit_cost, 4),
        high_usd=round(emit_cost, 4),
    )

    return CostEstimate(
        per_phase=[ingest, transform, link, qa, emit],
        buffer_pct=buffer_pct,
    )
