from builder.transform.extractor import ConceptExtractor


def test_extractor_returns_body_and_usage(canned_agent):
    canned_agent.recipes["Target concept"] = (
        "# OAuth2 Flow\n\nOAuth2 separates authn and authz.\n"
    )
    ext = ConceptExtractor(agent=canned_agent)

    body, usage = ext.extract(
        source_text="OAuth2 details...",
        source_name="handbook.md",
        concept_name="oauth2-flow",
        concept_title="OAuth2 Flow",
    )

    assert "OAuth2" in body
    assert usage.input_tokens > 0
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_extractor_strips_code_fences(canned_agent):
    """Body responses wrapped in fences should be unwrapped."""
    canned_agent.recipes["Target"] = (
        "```markdown\n# Hello\n\nBody.\n```"
    )
    ext = ConceptExtractor(agent=canned_agent)
    body, _ = ext.extract(
        source_text="x", source_name="doc",
        concept_name="c", concept_title="C",
    )
    assert not body.startswith("```")
    assert "# Hello" in body
