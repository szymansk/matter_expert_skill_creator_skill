"""Coverage checker — verifies all source-outline topics got extracted."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.prompts import coverage_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class CoverageError(Exception):
    """Raised when the coverage check response cannot be parsed."""


class CoverageChecker:
    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def check(
        self,
        source_outline: list[str],
        extracted_titles: list[str],
    ) -> tuple[list[str], AgentResponse]:
        prompt = coverage_prompt(
            source_outline=source_outline,
            extracted_concept_titles=extracted_titles,
        )
        response = self._agent.call(prompt, model="haiku")
        missed = self._parse(response.text)
        return missed, response

    def _parse(self, text: str) -> list[str]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise CoverageError(f"could not parse coverage JSON: {e}") from e
        if not isinstance(data, dict) or "missed_topics" not in data:
            raise CoverageError("coverage JSON missing 'missed_topics' key")
        return list(data["missed_topics"])
