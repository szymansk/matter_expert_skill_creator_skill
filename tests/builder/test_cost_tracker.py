from builder.cost_tracker import (
    TokenUsage,
    MODEL_PRICES_USD_PER_MILLION,
    estimate_cost,
    format_cost_breakdown,
)
from builder.phases import Model, Phase


def test_token_usage_construction():
    usage = TokenUsage(input_tokens=1000, output_tokens=500)
    assert usage.input_tokens == 1000
    assert usage.output_tokens == 500
    assert usage.cached_input_tokens == 0


def test_token_usage_with_cached_tokens():
    usage = TokenUsage(
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=200,
    )
    assert usage.cached_input_tokens == 200


def test_model_prices_cover_all_models():
    for model in Model:
        assert model in MODEL_PRICES_USD_PER_MILLION
        assert "input" in MODEL_PRICES_USD_PER_MILLION[model]
        assert "output" in MODEL_PRICES_USD_PER_MILLION[model]


def test_estimate_cost_haiku():
    """Haiku at default prices: 1M input + 1M output @ $1/$5 per million."""
    usage = TokenUsage(input_tokens=1_000_000, output_tokens=1_000_000)
    cost = estimate_cost(Model.HAIKU, usage)
    expected = (
        MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["input"]
        + MODEL_PRICES_USD_PER_MILLION[Model.HAIKU]["output"]
    )
    assert cost == expected


def test_estimate_cost_zero_tokens():
    cost = estimate_cost(Model.SONNET, TokenUsage(input_tokens=0, output_tokens=0))
    assert cost == 0.0


def test_estimate_cost_cached_input_is_cheaper():
    """Cached input tokens cost 10% of regular input tokens."""
    regular = estimate_cost(
        Model.SONNET,
        TokenUsage(input_tokens=1_000_000, output_tokens=0),
    )
    cached = estimate_cost(
        Model.SONNET,
        TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cached_input_tokens=1_000_000,
        ),
    )
    assert cached < regular
    assert cached == regular * 0.1


def test_format_cost_breakdown_simple():
    breakdown = {
        Phase.INGEST: 0.50,
        Phase.TRANSFORM: 4.20,
        Phase.LINK: 1.80,
        Phase.QA: 0.60,
        Phase.EMIT: 0.30,
    }
    output = format_cost_breakdown(breakdown, buffer_pct=0.20)

    assert "ingest" in output.lower()
    assert "transform" in output.lower()
    assert "link" in output.lower()
    assert "qa" in output.lower()
    assert "emit" in output.lower()
    assert "buffer" in output.lower() or "puffer" in output.lower()
    # Buffer is 20% of subtotal 7.40 = 1.48
    # Total is 7.40 + 1.48 = 8.88
    assert "8.88" in output


def test_format_cost_breakdown_zero_buffer():
    breakdown = {Phase.INGEST: 1.0, Phase.EMIT: 1.0}
    output = format_cost_breakdown(breakdown, buffer_pct=0.0)
    assert "2.00" in output
