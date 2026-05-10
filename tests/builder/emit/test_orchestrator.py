import json
from datetime import date
from pathlib import Path

from builder.emit.orchestrator import EmitOrchestrator, EmitConfig
from builder.phases import Phase
from builder.pipeline import Pipeline
from matter_expert import (
    ConceptFrontmatter, ConceptPage, MOCFrontmatter, MOCPage,
    Source, SourceFrontmatter, SourcePage, VaultPaths,
)


def _build_vault(root: Path) -> VaultPaths:
    paths = VaultPaths(root=root)
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    fm = ConceptFrontmatter(
        title="OAuth2",
        sources=[Source(file="handbook.md", sections=["3.1"])],
        tags=["auth"], created=date(2026, 5, 10),
    )
    ConceptPage(frontmatter=fm, body="# OAuth2\n\nbody",
                path=paths.concept_for("oauth2-flow")).write()

    moc = MOCPage(
        frontmatter=MOCFrontmatter(
            title="Auth", children=["oauth2-flow"],
            parents=[], related_mocs=[], created=date(2026, 5, 10),
        ),
        body="# Auth MOC\n", path=paths.mocs / "auth.md",
    )
    moc.write()

    src = SourcePage(
        frontmatter=SourceFrontmatter(
            title="Handbook", original_file="handbook.pdf",
            original_format="pdf", page_count=1,
            extraction_method="text", language_detected="en",
            ingested=date(2026, 5, 10),
        ),
        body="Handbook body", path=paths.source_for("handbook"),
    )
    src.write()
    return paths


def test_orchestrator_produces_full_plugin_structure(
    tmp_path: Path, canned_agent, run_dir,
):
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"

    cfg = EmitConfig(
        plugin_name="oauth-expert",
        plugin_version="0.1.0",
        plugin_description="Expert on OAuth and JWT.",
        author="builder",
    )
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(agent=canned_agent, config=cfg)

    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)

    # Top-level structure.
    assert (plugin_root / ".claude-plugin" / "plugin.json").exists()
    assert (plugin_root / "README.md").exists()
    # Skill directory
    skill = plugin_root / "skills" / "oauth-expert"
    assert (skill / "SKILL.md").exists()
    # Bundled vault
    assert (skill / "vault" / "concepts" / "oauth2-flow.md").exists()
    assert (skill / "vault" / "MOCs" / "auth.md").exists()
    assert (skill / "vault" / "sources" / "handbook.md").exists()
    # Index files
    assert (skill / "_index" / "concept_index.json").exists()
    assert (skill / "_index" / "moc_map.json").exists()
    assert (skill / "_index" / "link_graph.json").exists()
    assert (skill / "_index" / "alias_map.json").exists()
    # Bundled runtime (preserved as scripts/runtime/ package)
    assert (skill / "scripts" / "runtime" / "vault_locate.py").exists()
    assert (skill / "scripts" / "runtime" / "vault_brainstorm.py").exists()
    # Initial memory
    assert (skill / "memory" / "query_cache.json").exists()
    assert (skill / "memory" / "user_preferences.json").exists()


def test_orchestrator_marks_phase_complete_in_pipeline(
    tmp_path: Path, canned_agent, run_dir,
):
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(
        agent=canned_agent,
        config=EmitConfig(plugin_name="x", plugin_version="0.1.0",
                            plugin_description="d", author="a"),
    )
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)
    assert pipeline.is_phase_complete(Phase.EMIT)


def test_orchestrator_records_cost_for_skill_md(
    tmp_path: Path, canned_agent, run_dir,
):
    """SKILL.md trigger description is LLM-generated → cost > 0."""
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(
        agent=canned_agent,
        config=EmitConfig(plugin_name="x", plugin_version="0.1.0",
                            plugin_description="d", author="a"),
    )
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline)
    assert pipeline.state.cost_tracker["per_phase"].get("emit", 0) > 0


def test_emit_is_idempotent(tmp_path: Path, canned_agent, run_dir):
    """Calling emit() twice into the same plugin_root must not raise."""
    vault_paths = _build_vault(tmp_path / "vault")
    plugin_root = tmp_path / "out_plugin"
    cfg = EmitConfig(plugin_name="idempotent-expert", plugin_version="0.1.0",
                     plugin_description="d", author="a")

    pipeline1 = Pipeline.create(
        run_id="x1", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = EmitOrchestrator(agent=canned_agent, config=cfg)
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline1)

    # Second emit into the same plugin_root — must overwrite cleanly.
    run_dir2 = tmp_path / "run2"
    run_dir2.mkdir()
    pipeline2 = Pipeline.create(
        run_id="x2", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir2,
    )
    orch.emit(vault=vault_paths, plugin_root=plugin_root, pipeline=pipeline2)

    skill = plugin_root / "skills" / "idempotent-expert"
    assert (skill / "scripts" / "runtime" / "vault_locate.py").exists()
    assert (skill / "_index" / "concept_index.json").exists()
    assert (skill / "memory" / "query_cache.json").exists()
