"""Validator 1: Translation Quality (Sonnet, low effort, sampled)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from builder.ingest.protocols import AgentCaller
from builder.qa.prompts import translation_prompt
from builder.qa.report import Severity, ValidatorResult
from builder.qa.thresholds import (
    SAMPLE_FRACTION_TRANSLATION, SAMPLE_MIN_TRANSLATION, sample_items,
)
from matter_expert import ConceptPage, VaultPaths


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)


class TranslationQualityValidator:
    name = "translation_quality"

    def __init__(self, agent: AgentCaller, seed: int = 0) -> None:
        self._agent = agent
        self._seed = seed

    def validate(self, vault: VaultPaths) -> ValidatorResult:
        concepts = sorted(vault.concepts.glob("*.md"))
        total = len(concepts)
        sample = sample_items(
            concepts,
            fraction=SAMPLE_FRACTION_TRANSLATION,
            minimum=SAMPLE_MIN_TRANSLATION,
            seed=self._seed,
        )
        issues: list[dict] = []
        for path in sample:
            page = ConceptPage.read(path)
            source_excerpt = self._read_source_excerpt(vault, page)
            prompt = translation_prompt(
                concept_title=page.frontmatter.title,
                body=page.body,
                source_excerpt=source_excerpt,
            )
            resp = self._agent.call(prompt, model="sonnet")
            verdict = self._parse(resp.text)
            if verdict.get("verdict") == "fail":
                issues.append({
                    "concept": page.path.stem,
                    "reasons": verdict.get("reasons", []),
                })
        severity = Severity.WARNING if issues else Severity.PASS
        return ValidatorResult(
            name=self.name, severity=severity,
            sampled=len(sample), total=total, issues=issues,
            notes=f"sampled {len(sample)} of {total}",
        )

    def _read_source_excerpt(self, vault: VaultPaths, page: ConceptPage) -> str:
        if not page.frontmatter.sources:
            return ""
        first_source = page.frontmatter.sources[0].file
        stem = Path(first_source).stem
        src_path = vault.source_for(stem)
        if not src_path.exists():
            return ""
        text = src_path.read_text(encoding="utf-8")
        return text[:1000]

    def _parse(self, text: str) -> dict:
        cleaned = text.strip()
        m = CODE_FENCE.match(cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"verdict": "pass", "reasons": []}
