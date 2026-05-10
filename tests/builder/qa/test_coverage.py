import json

from builder.qa.coverage import CoverageValidator
from builder.qa.report import Severity


def test_coverage_passes_when_no_missed_topics(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"missed_topics": []})
    v = CoverageValidator(agent=canned_agent)
    # Coverage check expects source-doc → outline pairs; here we provide an empty
    # mapping so the validator simply reports pass (no sources to check).
    result = v.validate(vault=populated_vault, source_outlines={})
    assert result.severity == Severity.PASS


def test_coverage_warns_on_missed_topics(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"missed_topics": ["edge-cases"]})
    v = CoverageValidator(agent=canned_agent)
    outlines = {"handbook.md": ["Auth", "Edge Cases"]}
    result = v.validate(vault=populated_vault, source_outlines=outlines)
    assert result.severity == Severity.WARNING
    assert any("edge-cases" in str(i) for i in result.issues)


def test_coverage_uses_haiku(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"missed_topics": []})
    v = CoverageValidator(agent=canned_agent)
    v.validate(vault=populated_vault, source_outlines={"x.md": ["a"]})
    assert all(c["model"] == "haiku" for c in canned_agent.calls)
