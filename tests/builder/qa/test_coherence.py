import json

from builder.qa.coherence import ConceptCoherenceValidator
from builder.qa.report import Severity


def test_coherence_passes(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "issues": []})
    v = ConceptCoherenceValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.PASS


def test_coherence_warns_when_issues_found(populated_vault, canned_agent):
    canned_agent.default = json.dumps({
        "verdict": "fail", "issues": ["unexplained 'as mentioned above'"],
    })
    v = ConceptCoherenceValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.WARNING
    assert len(result.issues) >= 1


def test_coherence_uses_sonnet(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "issues": []})
    v = ConceptCoherenceValidator(agent=canned_agent, seed=42)
    v.validate(vault=populated_vault)
    assert all(c["model"] == "sonnet" for c in canned_agent.calls)
