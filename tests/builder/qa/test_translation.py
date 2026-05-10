import json
from pathlib import Path

from builder.qa.report import Severity
from builder.qa.translation import (
    DEFAULT_FAIL_THRESHOLD_PCT,
    SAMPLE_MAX_TRANSLATION,
    TranslationQualityValidator,
)


def test_validator_returns_pass_when_all_translations_ok(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": []})

    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)

    assert result.severity == Severity.PASS
    assert result.sampled >= 1
    assert result.issues == []


def test_validator_returns_warning_when_some_fail_below_threshold(
    populated_vault, canned_agent
):
    """One failure out of 3 sampled = 33% — but with threshold set high enough,
    we only get a WARNING (not FAIL) to test the sub-threshold branch."""
    # Set a very high threshold so one-of-three (33%) is still below it.
    # With the default 5% threshold and 3 concepts, 1 fail = 33% → FAIL.
    # We override to 50% so that 1/3 (33%) < 50% → WARNING.
    from builder.ingest.protocols import AgentResponse

    call_count = []

    def calls(prompt, *, model="haiku", images=None):
        canned_agent.calls.append({"prompt": prompt, "model": model})
        call_count.append(1)
        if len(call_count) == 1:
            return AgentResponse(
                text=json.dumps({"verdict": "fail", "reasons": ["awkward"]}),
                input_tokens=100, output_tokens=50,
            )
        return AgentResponse(
            text=json.dumps({"verdict": "pass", "reasons": []}),
            input_tokens=100, output_tokens=50,
        )

    canned_agent.call = calls  # type: ignore

    v = TranslationQualityValidator(agent=canned_agent, seed=42, fail_threshold_pct=50.0)
    result = v.validate(vault=populated_vault)

    assert result.severity == Severity.WARNING
    assert len(result.issues) >= 1


def test_validator_returns_fail_above_threshold(populated_vault, canned_agent):
    """All 3 concepts fail → 100% fail rate > 5% threshold → FAIL severity."""
    canned_agent.default = json.dumps({"verdict": "fail", "reasons": ["bad"]})

    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)

    assert result.severity == Severity.FAIL
    assert len(result.issues) == 3


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


def test_sample_cap_constants():
    """Spec §4.5: 5%, min 10, max 50."""
    assert DEFAULT_FAIL_THRESHOLD_PCT == 5.0
    assert SAMPLE_MAX_TRANSLATION == 50


def test_notes_include_fail_rate(populated_vault, canned_agent):
    canned_agent.default = json.dumps({"verdict": "pass", "reasons": []})
    v = TranslationQualityValidator(agent=canned_agent, seed=42)
    result = v.validate(vault=populated_vault)
    assert "fail rate" in result.notes
    assert "threshold" in result.notes
