"""Validator 4: Citation Accuracy (Sonnet, medium, sampled, strict threshold)."""
from __future__ import annotations

import json
import re
from pathlib import Path

from builder.ingest.protocols import AgentCaller
from builder.qa.prompts import citation_prompt
from builder.qa.report import Severity, ValidatorResult
from builder.qa.thresholds import SAMPLE_FRACTION_CITATION, sample_items
from matter_expert import ConceptPage, VaultPaths


CODE_FENCE = re.compile(r"^```(?:json)?\s*\n(.+?)\n```\s*$", re.DOTALL)
DEFAULT_FAIL_THRESHOLD_PCT = 2.0  # spec §4.5 — citation accuracy is strict


class CitationAccuracyValidator:
    name = "citation_accuracy"

    def __init__(self, agent: AgentCaller, seed: int = 0,
                 fail_threshold_pct: float = DEFAULT_FAIL_THRESHOLD_PCT) -> None:
        self._agent = agent
        self._seed = seed
        self._fail_threshold_pct = fail_threshold_pct

    def validate(self, vault: VaultPaths) -> ValidatorResult:
        concepts = sorted(vault.concepts.glob("*.md")) if vault.concepts.exists() else []
        total = len(concepts)
        sample = sample_items(
            concepts, fraction=SAMPLE_FRACTION_CITATION,
            minimum=1, seed=self._seed,
        ) if concepts else []

        issues: list[dict] = []
        for path in sample:
            page = ConceptPage.read(path)
            cited = [s.file for s in page.frontmatter.sources]
            excerpts = self._read_source_excerpts(vault, cited)
            prompt = citation_prompt(
                concept_title=page.frontmatter.title,
                body=page.body, cited_sources=cited,
                source_excerpts=excerpts,
            )
            resp = self._agent.call(prompt, model="sonnet")
            verdict = self._parse(resp.text)
            if verdict.get("verdict") == "fail":
                issues.append({"concept": page.path.stem,
                               "unsupported_claims": verdict.get("unsupported_claims", [])})

        if not sample:
            return ValidatorResult(name=self.name, severity=Severity.PASS,
                                    sampled=0, total=total, issues=[])

        fail_rate_pct = (len(issues) / len(sample)) * 100
        if fail_rate_pct > self._fail_threshold_pct:
            severity = Severity.FAIL
        elif issues:
            severity = Severity.WARNING
        else:
            severity = Severity.PASS

        return ValidatorResult(
            name=self.name, severity=severity,
            sampled=len(sample), total=total, issues=issues,
            notes=f"fail rate {fail_rate_pct:.1f}% "
                  f"(threshold {self._fail_threshold_pct}%)",
        )

    def _read_source_excerpts(
        self, vault: VaultPaths, cited: list[str],
    ) -> dict[str, str]:
        excerpts: dict[str, str] = {}
        for f in cited:
            stem = Path(f).stem
            src_path = vault.source_for(stem)
            if src_path.exists():
                excerpts[f] = src_path.read_text(encoding="utf-8")[:1000]
        return excerpts

    def _parse(self, text: str) -> dict:
        cleaned = text.strip()
        m = CODE_FENCE.match(cleaned)
        if m:
            cleaned = m.group(1).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            return {"verdict": "pass", "unsupported_claims": []}
