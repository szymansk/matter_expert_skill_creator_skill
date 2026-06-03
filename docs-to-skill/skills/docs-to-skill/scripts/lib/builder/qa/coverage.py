"""Validator 3: Coverage Check (Haiku, medium, per source document)."""
from __future__ import annotations

import json
import re

from builder.ingest.protocols import AgentCaller
from builder.qa.prompts import coverage_prompt
from builder.qa.report import Severity, ValidatorResult
from matter_expert import ConceptPage, VaultPaths


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class CoverageValidator:
    name = "coverage"

    def __init__(self, agent: AgentCaller) -> None:
        self._agent = agent

    def validate(
        self,
        vault: VaultPaths,
        source_outlines: dict[str, list[str]],
    ) -> ValidatorResult:
        all_titles = self._extracted_titles(vault)
        issues: list[dict] = []
        for source_id, outline in source_outlines.items():
            prompt = coverage_prompt(outline, all_titles)
            resp = self._agent.call(prompt, model="haiku")
            missed = self._parse(resp.text)
            if missed:
                issues.append({"source": source_id, "missed_topics": missed})
        severity = Severity.WARNING if issues else Severity.PASS
        return ValidatorResult(
            name=self.name, severity=severity,
            sampled=len(source_outlines), total=len(source_outlines),
            issues=issues,
        )

    def _extracted_titles(self, vault: VaultPaths) -> list[str]:
        if not vault.concepts.exists():
            return []
        return [ConceptPage.read(p).frontmatter.title
                for p in sorted(vault.concepts.glob("*.md"))]

    def _parse(self, text: str) -> list[str]:
        cleaned = text.strip()
        m = CODE_FENCE.match(cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        return list(data.get("missed_topics", []))
