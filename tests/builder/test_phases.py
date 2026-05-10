from builder.phases import (
    Phase,
    Model,
    Effort,
    PhaseConfig,
    DEFAULT_CONFIGS,
    config_for_phase,
)


def test_phase_enum_has_five_values():
    assert {p.value for p in Phase} == {
        "ingest", "transform", "link", "qa", "emit"
    }


def test_phase_enum_iteration_order_matches_pipeline_order():
    assert list(Phase) == [
        Phase.INGEST,
        Phase.TRANSFORM,
        Phase.LINK,
        Phase.QA,
        Phase.EMIT,
    ]


def test_model_enum_values():
    assert {m.value for m in Model} == {"haiku", "sonnet", "opus"}


def test_effort_enum_values():
    assert {e.value for e in Effort} == {"low", "medium", "high"}


def test_phase_config_construction():
    cfg = PhaseConfig(phase=Phase.INGEST, model=Model.HAIKU, effort=Effort.LOW)
    assert cfg.phase == Phase.INGEST
    assert cfg.model == Model.HAIKU
    assert cfg.effort == Effort.LOW


def test_default_configs_have_one_per_phase():
    phases_in_defaults = {cfg.phase for cfg in DEFAULT_CONFIGS}
    assert phases_in_defaults == set(Phase)
    assert len(DEFAULT_CONFIGS) == 5


def test_default_configs_match_design_spec():
    by_phase = {cfg.phase: cfg for cfg in DEFAULT_CONFIGS}
    assert by_phase[Phase.INGEST].model == Model.HAIKU
    assert by_phase[Phase.INGEST].effort == Effort.LOW
    assert by_phase[Phase.TRANSFORM].model == Model.HAIKU
    assert by_phase[Phase.TRANSFORM].effort == Effort.MEDIUM
    assert by_phase[Phase.LINK].model == Model.SONNET
    assert by_phase[Phase.LINK].effort == Effort.HIGH
    assert by_phase[Phase.QA].model == Model.SONNET
    assert by_phase[Phase.QA].effort == Effort.MEDIUM
    assert by_phase[Phase.EMIT].model == Model.SONNET
    assert by_phase[Phase.EMIT].effort == Effort.HIGH


def test_config_for_phase_lookup():
    cfg = config_for_phase(Phase.LINK, DEFAULT_CONFIGS)
    assert cfg.phase == Phase.LINK
    assert cfg.model == Model.SONNET


def test_config_for_phase_missing_raises():
    import pytest
    custom = [PhaseConfig(Phase.INGEST, Model.HAIKU, Effort.LOW)]
    with pytest.raises(KeyError):
        config_for_phase(Phase.LINK, custom)
