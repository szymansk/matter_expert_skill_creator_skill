import json
import pytest

from builder.link.clusters import Cluster, ClusterIdentifier, ClusterError
from builder.link.inventory import ConceptSummary


def test_cluster_construction():
    c = Cluster(members=["oauth2-flow", "oauth-overview"])
    assert len(c.members) == 2


def test_identify_returns_clusters(canned_agent):
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [{"members": ["oauth2-flow", "oauth-overview"]}]
    })
    identifier = ClusterIdentifier(agent=canned_agent)
    inv = [
        ConceptSummary("oauth2-flow", "OAuth2", "OAuth2 framework.", []),
        ConceptSummary("oauth-overview", "OAuth Overview", "Overview of OAuth.", []),
        ConceptSummary("jwt-tokens", "JWT", "JSON Web Tokens.", []),
    ]
    clusters, usage = identifier.identify(inv)

    assert len(clusters) == 1
    assert set(clusters[0].members) == {"oauth2-flow", "oauth-overview"}
    assert usage.input_tokens > 0
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_identify_handles_no_clusters(canned_agent):
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    identifier = ClusterIdentifier(agent=canned_agent)
    clusters, _ = identifier.identify([])
    assert clusters == []


def test_identify_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    identifier = ClusterIdentifier(agent=canned_agent)
    with pytest.raises(ClusterError):
        identifier.identify([])


def test_identify_strips_singleton_clusters(canned_agent):
    """A 'cluster' with one member is not a duplication — drop it."""
    canned_agent.recipes["Inventory"] = json.dumps({
        "clusters": [
            {"members": ["a"]},
            {"members": ["b", "c"]},
        ]
    })
    identifier = ClusterIdentifier(agent=canned_agent)
    clusters, _ = identifier.identify([])
    # Only the 2-member cluster survives.
    assert len(clusters) == 1
    assert set(clusters[0].members) == {"b", "c"}
