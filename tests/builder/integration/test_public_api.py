def test_integration_public_api():
    from builder.integration import (
        CostEstimate, PhaseEstimate, estimate_build_cost,
        UrllibFetcher,
        AnthropicAgent, MODEL_ID_MAP,
        BuildConfig, BuilderOrchestrator,
    )
    assert callable(estimate_build_cost)
    assert "haiku" in MODEL_ID_MAP
