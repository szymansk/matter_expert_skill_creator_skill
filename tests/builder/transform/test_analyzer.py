import json

import pytest

from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.outline import ConceptOutline


def test_analyzer_returns_outline(canned_agent, outline_json_response):
    canned_agent.recipes["Identify the atomic concepts"] = outline_json_response
    analyzer = ConceptAnalyzer(agent=canned_agent)

    outline, usage = analyzer.analyze(
        source_text="OAuth2 is a framework.",
        source_name="handbook.md",
    )

    assert isinstance(outline, ConceptOutline)
    assert len(outline) == 2
    names = [e.concept_name for e in outline]
    assert "oauth2-flow" in names
    assert "jwt-tokens" in names
    assert usage.input_tokens > 0
    assert usage.output_tokens > 0


def test_analyzer_uses_haiku_low_effort(canned_agent, outline_json_response):
    canned_agent.recipes["Identify"] = outline_json_response
    analyzer = ConceptAnalyzer(agent=canned_agent)

    analyzer.analyze(source_text="x", source_name="doc")
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_analyzer_rejects_malformed_json(canned_agent):
    canned_agent.default = "not valid json {{"
    analyzer = ConceptAnalyzer(agent=canned_agent)

    with pytest.raises(AnalyzerError):
        analyzer.analyze(source_text="x", source_name="doc")


def test_analyzer_strips_code_fences(canned_agent):
    """Models often wrap JSON in ```json fences; analyzer should tolerate this."""
    canned_agent.default = (
        "```json\n"
        + json.dumps({"entries": []})
        + "\n```"
    )
    analyzer = ConceptAnalyzer(agent=canned_agent)
    outline, _ = analyzer.analyze(source_text="x", source_name="doc")
    assert isinstance(outline, ConceptOutline)
    assert len(outline) == 0
