import json

from builder.qa.citation import CitationAccuracyValidator
from builder.qa.report import Severity


def test_citation_passes(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "unsupported_claims": []})
    v = CitationAccuracyValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.PASS


def test_citation_fails_above_threshold(populated_vault, canned_agent):
    """A high fail rate triggers FAIL severity (citation accuracy is strict)."""
    canned_agent.default = json.dumps({
        "verdict": "fail", "unsupported_claims": ["claim x"],
    })
    v = CitationAccuracyValidator(agent=canned_agent, seed=42,
                                    fail_threshold_pct=10.0)
    result = v.validate(vault=populated_vault)
    # 100% fail >> 10% threshold → severity FAIL
    assert result.severity == Severity.FAIL
