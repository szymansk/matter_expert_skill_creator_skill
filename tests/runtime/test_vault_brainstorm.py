import json
import subprocess
import sys
from pathlib import Path

from runtime.vault_brainstorm import brainstorm


def test_brainstorm_returns_required_keys(built_indexes, vault_dir: Path, memory_dir: Path):
    """Every brainstorm output has the 5 required structural fields."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert "relevant_concepts" in result
    assert "clusters" in result
    assert "contradictions" in result
    assert "gaps" in result
    assert "entry_questions" in result


def test_brainstorm_finds_relevant_concepts_via_locate_and_traverse(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """The brainstorm topic 'authentication' is a MOC, so it surfaces all auth concepts."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    relevant = result["relevant_concepts"]
    names = {c["name"] for c in relevant}
    assert "oauth2-flow" in names
    assert "jwt-tokens" in names


def test_brainstorm_clusters_concepts_by_shared_tag(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """Concepts sharing tags should appear in the same cluster."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    clusters = result["clusters"]
    assert len(clusters) >= 1

    for cluster in clusters:
        assert "tag" in cluster
        assert "concepts" in cluster
        assert isinstance(cluster["concepts"], list)


def test_brainstorm_flags_concepts_with_multiple_sources_as_contradiction_candidates(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """oauth2-flow has two sources in the example vault — flag it for review."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    candidate_names = {c["concept"] for c in result["contradictions"]}
    assert "oauth2-flow" in candidate_names


def test_brainstorm_reports_topic_with_no_match_as_gap(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """A topic completely outside the vault should appear in gaps."""
    result = brainstorm(
        topic="quantum cryptography lattice resistance",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert result["relevant_concepts"] == []
    assert any("quantum" in g.lower() or "no match" in g.lower() for g in result["gaps"])


def test_brainstorm_proposes_entry_questions_for_broad_topic(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """A broad topic with many matches yields clarifying entry questions."""
    result = brainstorm(
        topic="authentication",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert isinstance(result["entry_questions"], list)
    if len(result["relevant_concepts"]) > 3:
        assert len(result["entry_questions"]) >= 1


def test_brainstorm_does_not_falsely_report_gap_when_topic_matched(
    built_indexes, vault_dir: Path, memory_dir: Path
):
    """A topic that matches a MOC name should not produce a 'no match' gap,
    even if the MOC's children list is empty."""
    # The example vault's 'security' MOC has children=[] in its frontmatter.
    # Edit the moc_map to confirm the empty case behaves correctly.
    import json
    moc_path = built_indexes.moc_map
    mocs = json.loads(moc_path.read_text())
    mocs["empty-moc"] = {"path": "MOCs/empty-moc.md", "children": [], "parents": []}
    moc_path.write_text(json.dumps(mocs, indent=2, sort_keys=True))

    result = brainstorm(
        topic="empty-moc",
        index_dir=built_indexes.index_dir,
        vault_dir=vault_dir,
        memory_dir=memory_dir,
    )
    assert result["strategy"] == "moc_match"
    # Must NOT contain the false "no match" message
    assert not any("no match in vault" in g for g in result["gaps"])


def test_cli_outputs_json(built_indexes, vault_dir: Path, memory_dir: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_brainstorm",
            "--index-dir", str(built_indexes.index_dir),
            "--vault", str(vault_dir),
            "--memory-dir", str(memory_dir),
            "--topic", "authentication",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert "relevant_concepts" in parsed
