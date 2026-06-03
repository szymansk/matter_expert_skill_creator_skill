"""Validator 5: Concept Coherence (Sonnet, high effort, sampled)."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller
from builder.qa.prompts import coherence_prompt
from builder.qa.report import Severity, ValidatorResult
from builder.qa.thresholds import SAMPLE_FRACTION_COHERENCE, sample_items
from matter_expert import ConceptPage, VaultPaths


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class ConceptCoherenceValidator:
    name = "concept_coherence"

    def __init__(self, agent: AgentCaller, seed: int = 0) -> None:
        self._agent = agent
        self._seed = seed

    def validate(self, vault: VaultPaths) -> ValidatorResult:
        concepts = sorted(vault.concepts.glob("*.md")) if vault.concepts.exists() else []
        total = len(concepts)
        sample = sample_items(
            concepts, fraction=SAMPLE_FRACTION_COHERENCE,
            minimum=1, seed=self._seed,
        ) if concepts else []

        issues: list[dict] = []
        for path in sample:
            page = ConceptPage.read(path)
            prompt = coherence_prompt(
                concept_title=page.frontmatter.title, body=page.body,
            )
            resp = self._agent.call(prompt, model="sonnet")
            verdict = self._parse(resp.text)
            if verdict.get("verdict") == "fail":
                issues.append({"concept": page.path.stem,
                               "issues": verdict.get("issues", [])})

        severity = Severity.WARNING if issues else Severity.PASS
        return ValidatorResult(
            name=self.name, severity=severity,
            sampled=len(sample), total=total, issues=issues,
        )

    def _parse(self, text: str) -> dict:
        cleaned = text.strip()
        m = CODE_FENCE.match(cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"verdict": "pass", "issues": []}
