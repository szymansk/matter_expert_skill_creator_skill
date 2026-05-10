def test_builder_public_api_exports():
    from builder import (
        Phase,
        Model,
        Effort,
        PhaseConfig,
        DEFAULT_CONFIGS,
        config_for_phase,
        TokenUsage,
        MODEL_PRICES_USD_PER_MILLION,
        estimate_cost,
        format_cost_breakdown,
        FailureClass,
        PipelineError,
        with_retry,
        ItemState,
        PhaseState,
        PipelineState,
        Pipeline,
    )

    assert issubclass(Phase, object)
    assert callable(estimate_cost)
    assert callable(with_retry)
    assert hasattr(Pipeline, "create")
    assert hasattr(Pipeline, "resume")
    assert hasattr(Pipeline, "replay_from")
