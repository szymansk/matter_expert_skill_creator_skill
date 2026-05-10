"""Assign typed links (related, prerequisites, examples, contrasts, refines)
for a single concept based on the full inventory."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.cardinality import enforce_link_cardinality
from builder.link.inventory import ConceptSummary
from builder.link.prompts import link_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)
LINK_KEYS = ("related", "prerequisites", "examples", "contrasts", "refines")


class LinkError(Exception):
    pass


class LinkAgent:
    """Assigns typed links for a single target concept."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def assign(
        self,
        target: ConceptSummary,
        inventory: list[ConceptSummary],
    ) -> tuple[dict[str, list[str]], AgentResponse]:
        inv_payload = [
            {"name": s.name, "title": s.title, "summary": s.summary}
            for s in inventory if s.name != target.name
        ]
        prompt = link_prompt(
            target_summary={
                "name": target.name, "title": target.title,
                "summary": target.summary,
            },
            inventory_json=json.dumps(inv_payload),
        )
        response = self._agent.call(prompt, model="sonnet")
        links = self._parse(response.text, target.name)
        return links, response

    def _parse(self, text: str, target_name: str) -> dict[str, list[str]]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LinkError(f"could not parse link JSON: {e}") from e
        if not isinstance(data, dict):
            raise LinkError("link JSON must be an object")

        # Fill missing keys with empty lists, drop self-references, dedupe.
        result: dict[str, list[str]] = {}
        for key in LINK_KEYS:
            raw_list = data.get(key, [])
            seen: set[str] = set()
            cleaned_list: list[str] = []
            for item in raw_list:
                if item == target_name or item in seen:
                    continue
                seen.add(item)
                cleaned_list.append(item)
            result[key] = cleaned_list
        return enforce_link_cardinality(result)
