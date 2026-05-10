"""Extractor — produces one concept's markdown body from a source doc."""
from __future__ import annotations

import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.transform.prompts import extractor_prompt


CODE_FENCE = re.compile(
    r"^```(?:markdown|md)?\s*\n(.+?)\n```\s*$",
    re.DOTALL,
)


class ConceptExtractor:
    """Extracts the markdown body for one concept from a source document."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def extract(
        self,
        source_text: str,
        source_name: str,
        concept_name: str,
        concept_title: str,
    ) -> tuple[str, AgentResponse]:
        prompt = extractor_prompt(
            source_text=source_text,
            source_name=source_name,
            concept_name=concept_name,
            concept_title=concept_title,
        )
        response = self._agent.call(prompt, model="haiku")
        body = self._strip_fence(response.text)
        return body, response

    def _strip_fence(self, text: str) -> str:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            return match.group(1)
        return cleaned
