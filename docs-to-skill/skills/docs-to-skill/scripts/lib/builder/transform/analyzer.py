"""Analyzer — turns a raw source document into a ConceptOutline (JSON)."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.outline import ConceptOutline
from builder.transform.prompts import analyzer_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class AnalyzerError(Exception):
    """Raised when the analyzer's response cannot be parsed."""


class ConceptAnalyzer:
    """Identifies atomic concepts in a source document via an LLM."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def analyze(
        self,
        source_text: str,
        source_name: str,
    ) -> tuple[ConceptOutline, AgentResponse]:
        prompt = analyzer_prompt(source_text, source_name)
        response = self._agent.call(prompt, model="haiku")
        outline = self._parse(response.text)
        return outline, response

    def _parse(self, text: str) -> ConceptOutline:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise AnalyzerError(f"could not parse analyzer JSON: {e}") from e
        if not isinstance(data, dict) or "entries" not in data:
            raise AnalyzerError("analyzer JSON missing 'entries' key")
        return ConceptOutline.from_dict(data)
