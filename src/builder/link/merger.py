"""Merge multiple concept pages into a single canonical page."""
from __future__ import annotations

import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.prompts import merge_prompt


CODE_FENCE = re.compile(
    r"^```(?:markdown|md)?\s*\n(.+?)\n```\s*$", re.DOTALL,
)


class ConceptMerger:
    """Merges a cluster of duplicate concept pages into one canonical page."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def merge(
        self,
        concepts: list[dict],
    ) -> tuple[dict, AgentResponse]:
        """Merge the given concept pages.

        Each item: {name, title, body, sources}.
        Returns ({body, sources, merged_from}, usage).
        """
        prompt = merge_prompt(concepts)
        response = self._agent.call(prompt, model="sonnet")
        body = self._strip_fence(response.text)

        # Aggregate sources from all input concepts.
        seen_files = set()
        aggregated: list[dict] = []
        for c in concepts:
            for src in c.get("sources", []):
                key = src.get("file")
                if key and key not in seen_files:
                    seen_files.add(key)
                    aggregated.append(src)

        merged_from = [c["name"] for c in concepts]
        return ({"body": body, "sources": aggregated, "merged_from": merged_from},
                response)

    def _strip_fence(self, text: str) -> str:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            return match.group(1)
        return cleaned
