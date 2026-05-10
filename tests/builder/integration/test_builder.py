from pathlib import Path

from builder.integration.builder import BuilderOrchestrator, BuildConfig
from builder.phases import Phase


def test_end_to_end_build_produces_plugin(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    config = BuildConfig(
        run_id="2026-05-10-test",
        input_dir=sample_input_dir,
        url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="test-skill",
        plugin_version="0.1.0",
        plugin_description="Test expert skill.",
        author="builder",
    )
    builder = BuilderOrchestrator(
        agent=full_pipeline_agent,
        fetcher=mock_fetcher,
    )
    pipeline = builder.build(config=config)

    # All 5 phases complete.
    for phase in Phase:
        assert pipeline.is_phase_complete(phase), f"phase {phase} not complete"

    # Plugin produced.
    assert (config.plugin_root / ".claude-plugin" / "plugin.json").exists()
    assert (config.plugin_root / "skills" / "test-skill" / "SKILL.md").exists()
    assert (config.plugin_root / "skills" / "test-skill" / "vault" / "concepts").exists()


def test_resume_skips_already_completed_phases(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    """Calling build() twice with the same run_dir resumes — completed phases
    do not re-run."""
    config = BuildConfig(
        run_id="x", input_dir=sample_input_dir, url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="x", plugin_version="0.1.0",
        plugin_description="d", author="a",
    )
    builder = BuilderOrchestrator(agent=full_pipeline_agent, fetcher=mock_fetcher)
    first = builder.build(config=config)
    calls_before = len(full_pipeline_agent.calls)

    # Build again; the second invocation should resume — but since all
    # phases already completed, no additional agent calls are made.
    second = builder.build(config=config)
    calls_after = len(full_pipeline_agent.calls)

    # No extra calls because resume sees all phases as completed.
    assert calls_after == calls_before


def test_build_replays_target_phase_when_requested(
    sample_input_dir: Path, full_pipeline_agent, mock_fetcher, tmp_path,
):
    config = BuildConfig(
        run_id="x", input_dir=sample_input_dir, url_list=[],
        run_dir=tmp_path / "run",
        plugin_root=tmp_path / "plugin",
        plugin_name="x", plugin_version="0.1.0",
        plugin_description="d", author="a",
        replay_from=Phase.LINK,
    )
    builder = BuilderOrchestrator(agent=full_pipeline_agent, fetcher=mock_fetcher)
    # First a clean build...
    builder.build(config=BuildConfig(
        run_id=config.run_id, input_dir=config.input_dir, url_list=[],
        run_dir=config.run_dir, plugin_root=config.plugin_root,
        plugin_name=config.plugin_name, plugin_version=config.plugin_version,
        plugin_description=config.plugin_description, author=config.author,
    ))
    calls_before = len(full_pipeline_agent.calls)

    # Now replay from LINK onwards.
    builder.build(config=config)
    # Replay re-runs Link + QA + Emit → at least Emit's SKILL.md call should fire.
    assert len(full_pipeline_agent.calls) > calls_before
