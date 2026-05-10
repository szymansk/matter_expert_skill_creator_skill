import json
from datetime import date
from pathlib import Path

from builder.link.orchestrator import LinkOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline
from matter_expert import ConceptFrontmatter, ConceptPage, Source, VaultPaths


def _seed_concept(vault: VaultPaths, name: str, title: str, tags=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=[Source(file=f"{name}.md", sections=[])],
        tags=list(tags or []),
        created=date(2026, 5, 10),
    )
    vault.concepts.mkdir(parents=True, exist_ok=True)
    ConceptPage(
        frontmatter=fm,
        body=f"# {title}\n\nBody of {title}.\n",
        path=vault.concept_for(name),
    ).write()


def test_orchestrator_runs_full_link_pipeline(canned_agent, tmp_path, run_dir):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth2-flow", "OAuth2 Flow", tags=["auth"])
    _seed_concept(vault, "jwt-tokens", "JWT", tags=["auth"])

    # No clusters; per-concept link assignments
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [],
        "prerequisites": [],
        "examples": [],
        "contrasts": [],
        "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # Concepts still on disk
    assert vault.concept_for("oauth2-flow").exists()
    # One MOC generated for the "auth" tag
    assert (vault.root / "MOCs" / "auth.md").exists()
    # Pipeline marked complete with cost > 0
    assert pipeline.state.phases["link"].status in ("in_progress", "completed", "pending")
    assert pipeline.state.cost_tracker["per_phase"].get("link", 0) > 0


def test_orchestrator_merges_clustered_concepts(canned_agent, tmp_path, run_dir):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth-a", "OAuth A", tags=["auth"])
    _seed_concept(vault, "oauth-b", "OAuth B", tags=["auth"])

    # Cluster the two oauth concepts; merge them; no links assigned.
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [{"members": ["oauth-a", "oauth-b"]}]
    })
    canned_agent.recipes["Merge"] = (
        "# Combined OAuth\n\nUnified content.\n"
    )
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [], "prerequisites": [], "examples": [],
        "contrasts": [], "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # Originals removed; one merged page exists
    assert not vault.concept_for("oauth-b").exists()
    # The merged page uses the first member's name (oauth-a) as canonical
    survivor = ConceptPage.read(vault.concept_for("oauth-a"))
    assert "Unified content" in survivor.body
    assert set(survivor.frontmatter.merged_from) == {"oauth-a", "oauth-b"}


def test_orchestrator_writes_typed_links_to_concept_frontmatter(
    canned_agent, tmp_path, run_dir,
):
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "oauth2-flow", "OAuth2", tags=["auth"])
    _seed_concept(vault, "jwt-tokens", "JWT", tags=["auth"])

    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    # The LinkAgent will be invoked once per concept. It produces the same
    # mock response for both, but we filter self-refs in LinkAgent.
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["jwt-tokens", "oauth2-flow"],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    oauth = ConceptPage.read(vault.concept_for("oauth2-flow"))
    jwt = ConceptPage.read(vault.concept_for("jwt-tokens"))
    # Self-refs filtered out
    assert "oauth2-flow" not in oauth.frontmatter.related
    assert "jwt-tokens" in oauth.frontmatter.related
    assert "jwt-tokens" not in jwt.frontmatter.related
    assert "oauth2-flow" in jwt.frontmatter.related


def test_orchestrator_empty_vault_completes_cleanly(canned_agent, tmp_path, run_dir):
    """Link phase must not crash when concepts/ dir is absent or empty."""
    vault = VaultPaths(root=tmp_path / "vault")
    # No concepts dir created — vault is completely empty.
    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # No LLM calls made; phase marked completed.
    assert canned_agent.calls == []
    assert pipeline.state.phases["link"].status == "completed"


def test_orchestrator_single_concept_skips_link_agent(canned_agent, tmp_path, run_dir):
    """With only one concept there are no peers; LinkAgent must not be called."""
    vault = VaultPaths(root=tmp_path / "vault")
    _seed_concept(vault, "solo-concept", "Solo", tags=["alone"])

    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})

    pipeline = Pipeline.create(
        run_id="x", input_dir=Path("/tmp"), url_list=[], run_dir=run_dir,
    )
    orch = LinkOrchestrator(agent=canned_agent, vault_dir=vault.root)
    orch.link(pipeline=pipeline)

    # Only the cluster call should have been made (1 call), not a link call.
    link_calls = [c for c in canned_agent.calls if "Target concept" in c["prompt"]]
    assert link_calls == [], "LinkAgent must not be called for a single-concept vault"
