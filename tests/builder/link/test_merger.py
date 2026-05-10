import re

from builder.link.merger import ConceptMerger


def test_merger_returns_merged_body_and_aggregated_sources(canned_agent, tmp_path):
    canned_agent.recipes["Merge"] = "# OAuth2 Flow\n\nMerged content.\n"
    merger = ConceptMerger(agent=canned_agent)

    concepts = [
        {"name": "oauth2-flow", "title": "OAuth2 Flow",
         "body": "Body 1", "sources": [{"file": "a.pdf", "sections": ["1"]}]},
        {"name": "oauth-overview", "title": "OAuth Overview",
         "body": "Body 2", "sources": [{"file": "b.pdf", "sections": ["2"]}]},
    ]
    result, usage = merger.merge(concepts)

    assert "Merged content" in result["body"]
    # Sources from both inputs aggregated
    files = {s["file"] for s in result["sources"]}
    assert files == {"a.pdf", "b.pdf"}
    # Used sonnet for merging
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_merger_strips_code_fences(canned_agent):
    canned_agent.recipes["Merge"] = "```markdown\n# Merged\n\nBody.\n```"
    merger = ConceptMerger(agent=canned_agent)
    result, _ = merger.merge([
        {"name": "a", "title": "A", "body": "x", "sources": []},
        {"name": "b", "title": "B", "body": "y", "sources": []},
    ])
    assert not result["body"].startswith("```")
    assert "# Merged" in result["body"]


def test_merger_preserves_merged_from(canned_agent):
    """The merged concept records the names of the originals in merged_from."""
    canned_agent.recipes["Merge"] = "Body."
    merger = ConceptMerger(agent=canned_agent)
    result, _ = merger.merge([
        {"name": "a", "title": "A", "body": "x", "sources": []},
        {"name": "b", "title": "B", "body": "y", "sources": []},
    ])
    assert set(result["merged_from"]) == {"a", "b"}
