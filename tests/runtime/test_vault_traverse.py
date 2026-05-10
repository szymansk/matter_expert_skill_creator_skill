import json
import subprocess
import sys

from runtime.vault_traverse import traverse


def test_traverse_depth_zero_returns_starts_only(built_indexes):
    """Depth 0 returns just the starting set."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=0,
    )
    assert result == ["oauth2-flow"]


def test_traverse_depth_one_includes_directly_linked(built_indexes):
    """Depth 1 includes prerequisites, related, examples, etc."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
    )
    assert "oauth2-flow" in result
    assert "http-basics" in result
    assert "encryption-fundamentals" in result
    assert "jwt-tokens" in result
    assert "session-management" in result
    assert "oauth2-google-flow" in result
    assert "basic-auth" in result


def test_traverse_depth_two_grows_further(built_indexes):
    """Depth 2 follows links from depth-1 concepts."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=2,
    )
    assert len(result) >= 7


def test_traverse_filter_by_link_types(built_indexes):
    """Only follow specified link types."""
    result = traverse(
        starts=["oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
        include_types=["prerequisites"],
    )
    assert "oauth2-flow" in result
    assert "http-basics" in result
    assert "encryption-fundamentals" in result
    assert "jwt-tokens" not in result  # related is excluded
    assert "basic-auth" not in result  # contrasts is excluded


def test_traverse_includes_inverse_links(built_indexes):
    """leads_to (inverse of prerequisites) follows the graph backwards."""
    result = traverse(
        starts=["http-basics"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
        include_types=["leads_to"],
    )
    assert "oauth2-flow" in result
    assert "session-management" in result
    assert "basic-auth" in result


def test_traverse_unknown_start_concept_silently_dropped(built_indexes):
    """Starts that are not in the graph are dropped (no exception)."""
    result = traverse(
        starts=["does-not-exist", "oauth2-flow"],
        link_graph_path=built_indexes.link_graph,
        depth=1,
    )
    assert "oauth2-flow" in result
    assert "does-not-exist" not in result


def test_cli_outputs_json_list(built_indexes):
    result = subprocess.run(
        [
            sys.executable,
            "-m", "runtime.vault_traverse",
            "--link-graph", str(built_indexes.link_graph),
            "--depth", "1",
            "--from", "oauth2-flow",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    parsed = json.loads(result.stdout)
    assert isinstance(parsed, list)
    assert "oauth2-flow" in parsed
