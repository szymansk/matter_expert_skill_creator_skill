import json

import pytest

from builder.link.inventory import ConceptSummary
from builder.link.linker import LinkAgent, LinkError


def test_link_returns_typed_links(canned_agent):
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["jwt-tokens"],
        "prerequisites": ["http-basics"],
        "examples": ["oauth2-google-flow"],
        "contrasts": ["basic-auth"],
        "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)

    target = ConceptSummary("oauth2-flow", "OAuth2 Flow", "An auth framework.", [])
    inventory = [target, ConceptSummary("jwt-tokens", "JWT", "Tokens.", [])]
    links, usage = linker.assign(target, inventory)

    assert links["related"] == ["jwt-tokens"]
    assert links["prerequisites"] == ["http-basics"]
    assert canned_agent.calls[-1]["model"] == "sonnet"


def test_link_excludes_self(canned_agent):
    """If the LLM tries to link a concept to itself, it should be filtered out."""
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": ["oauth2-flow", "jwt-tokens"],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("oauth2-flow", "OAuth2", "...", [])
    links, _ = linker.assign(target, [target])
    assert "oauth2-flow" not in links["related"]
    assert "jwt-tokens" in links["related"]


def test_link_enforces_cardinality(canned_agent):
    """A response with too many 'related' entries is trimmed to the max."""
    canned_agent.recipes["Target concept"] = json.dumps({
        "related": [f"x{i}" for i in range(15)],
        "prerequisites": [], "examples": [], "contrasts": [], "refines": [],
    })
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "self", "...", [])
    links, _ = linker.assign(target, [])
    assert len(links["related"]) == 8  # MAX_RELATED


def test_link_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "S", "...", [])
    with pytest.raises(LinkError):
        linker.assign(target, [])


def test_link_fills_missing_keys_with_empty_lists(canned_agent):
    """If the LLM omits a key, the result still has all 5 keys."""
    canned_agent.recipes["Target"] = json.dumps({"related": ["a"]})
    linker = LinkAgent(agent=canned_agent)
    target = ConceptSummary("self", "S", "...", [])
    links, _ = linker.assign(target, [])
    for key in ("related", "prerequisites", "examples", "contrasts", "refines"):
        assert key in links
