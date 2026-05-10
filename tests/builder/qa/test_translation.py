import json
from pathlib import Path

from builder.qa.report import Severity
from builder.qa.translation import TranslationQualityValidator


def test_validator_returns_pass_when_all_translations_ok(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": []})

    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)

    assert result.severity == Severity.PASS
    assert result.sampled >= 1
    assert result.issues == []


def test_validator_returns_warning_when_some_fail(populated_vault, canned_agent):
    # First call says fail, second says pass.
    def calls(prompt, *, model="haiku", images=None):
        canned_agent.calls.append({"prompt": prompt, "model": model})
        from builder.ingest.protocols import AgentResponse
        # First call (whichever concept is sampled first) -> fail
        if len(canned_agent.calls) == 1:
            return AgentResponse(text=json.dumps({"verdict": "fail",
                                                   "reasons": ["awkward"]}),
                                  input_tokens=100, output_tokens=50)
        return AgentResponse(text=json.dumps({"verdict": "pass", "reasons": []}),
                              input_tokens=100, output_tokens=50)
    canned_agent.call = calls  # type: ignore

    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)

    assert result.severity == Severity.WARNING
    assert len(result.issues) >= 1


def test_validator_uses_sonnet_model(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": []})
    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    v.validate(vault=populated_vault)
    # Every call should target sonnet (low effort done via prompt style)
    assert all(c["model"] == "sonnet" for c in canned_agent.calls)


def test_validator_samples_minimum_even_for_small_vault(populated_vault, canned_agent):
    """5% of 3 = 0 → but minimum is 10 → bounded by len → 3 calls."""
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": []})
    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)
    # All 3 concepts in the fixture get sampled (3 < min 10).
    assert result.sampled == 3
