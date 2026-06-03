"""Identify clusters of duplicate/near-duplicate concepts via the LLM."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from builder.ingest.protocols import AgentCaller, AgentResponse
from builder.link.inventory import ConceptSummary
from builder.link.prompts import cluster_prompt


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class ClusterError(Exception):
    pass


@dataclass(frozen=True)
class Cluster:
    members: list[str]


class ClusterIdentifier:
    """Identifies groups of concepts that describe the same underlying thing."""

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def identify(
        self,
        inventory: list[ConceptSummary],
    ) -> tuple[list[Cluster], AgentResponse]:
        inv_payload = [
            {"name": s.name, "title": s.title, "summary": s.summary, "tags": s.tags}
            for s in inventory
        ]
        prompt = cluster_prompt(json.dumps(inv_payload))
        response = self._agent.call(prompt, model="sonnet")
        clusters = self._parse(response.text)
        return clusters, response

    def _parse(self, text: str) -> list[Cluster]:
        cleaned = text.strip()
        match = CODE_FENCE.match(cleaned)
        if match:
            cleaned = match.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ClusterError(f"could not parse cluster JSON: {e}") from e
        raw = data.get("clusters", [])
        clusters: list[Cluster] = []
        for entry in raw:
            members = list(entry.get("members", []))
            if len(members) > 1:
                clusters.append(Cluster(members=members))
        return clusters
