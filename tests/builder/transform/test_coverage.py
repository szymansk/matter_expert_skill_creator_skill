import json

import pytest

from builder.transform.coverage import CoverageChecker, CoverageError


def test_coverage_returns_empty_when_complete(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    checker = CoverageChecker(agent=canned_agent)

    missed, usage = checker.check(
        source_outline=["Intro", "Auth"],
        extracted_titles=["Intro", "Auth"],
    )

    assert missed == []
    assert usage.input_tokens > 0


def test_coverage_returns_missed_topics(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({
        "missed_topics": ["Edge Cases"],
    })
    checker = CoverageChecker(agent=canned_agent)

    missed, _ = checker.check(
        source_outline=["Intro", "Auth", "Edge Cases"],
        extracted_titles=["Intro", "Auth"],
    )

    assert missed == ["Edge Cases"]


def test_coverage_uses_haiku(canned_agent):
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    checker = CoverageChecker(agent=canned_agent)
    checker.check(source_outline=[], extracted_titles=[])
    assert canned_agent.calls[-1]["model"] == "haiku"


def test_coverage_rejects_malformed(canned_agent):
    canned_agent.default = "not json"
    checker = CoverageChecker(agent=canned_agent)
    with pytest.raises(CoverageError):
        checker.check(source_outline=[], extracted_titles=[])
