"""Cost estimation and tracking for the builder pipeline.

Pricing constants reflect Anthropic's per-million-token rates. Cached
input tokens cost 10% of normal input tokens (per Anthropic's prompt
caching docs). Adjust `MODEL_PRICES_USD_PER_MILLION` if prices change.
"""
from __future__ import annotations

from dataclasses import dataclass

from builder.phases import Model, Phase


CACHED_INPUT_DISCOUNT = 0.10  # cached input tokens cost 10% of normal


# Per-million-token prices in USD.
MODEL_PRICES_USD_PER_MILLION: dict[Model, dict[str, float]] = {
    Model.HAIKU: {"input": 1.0, "output": 5.0},
    Model.SONNET: {"input": 3.0, "output": 15.0},
    Model.OPUS: {"input": 15.0, "output": 75.0},
}


@dataclass(frozen=True)
class TokenUsage:
    """Token consumption of a single agent call."""
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


def estimate_cost(model: Model, usage: TokenUsage) -> float:
    """Estimate USD cost for `usage` on `model`."""
    prices = MODEL_PRICES_USD_PER_MILLION[model]
    per_million = 1_000_000

    input_cost = usage.input_tokens * prices["input"] / per_million
    output_cost = usage.output_tokens * prices["output"] / per_million
    cached_cost = (
        usage.cached_input_tokens
        / per_million
        * prices["input"]
        * CACHED_INPUT_DISCOUNT
    )
    return input_cost + output_cost + cached_cost


def format_cost_breakdown(
    per_phase_usd: dict[Phase, float],
    buffer_pct: float = 0.20,
) -> str:
    """Format a per-phase USD breakdown plus buffer + total as a human string."""
    lines = ["Estimated costs:"]
    subtotal = 0.0
    for phase in Phase:
        amount = per_phase_usd.get(phase, 0.0)
        lines.append(f"  {phase.value:<10} ${amount:>6.2f}")
        subtotal += amount

    buffer = subtotal * buffer_pct
    total = subtotal + buffer

    lines.append(f"  {'Buffer':<10} ${buffer:>6.2f}  ({int(buffer_pct * 100)}%)")
    lines.append(f"  {'─' * 17}")
    lines.append(f"  {'Total':<10} ${total:>6.2f}")
    return "\n".join(lines)
