"""QA orchestrator — runs all 6 validators, aggregates a QAReport."""
from __future__ import annotations

import json
from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.ingest.protocols import AgentCaller
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from builder.qa.citation import CitationAccuracyValidator
from builder.qa.coherence import ConceptCoherenceValidator
from builder.qa.coverage import CoverageValidator
from builder.qa.integrity import VaultIntegrityValidator
from builder.qa.link_resolution import LinkResolutionValidator
from builder.qa.report import QAReport
from builder.qa.translation import TranslationQualityValidator
from matter_expert import VaultPaths


class _CostTrackingAgent:
    """Wraps an AgentCaller to record cost-per-call to a Pipeline."""

    def __init__(self, inner: AgentCaller, pipeline: Pipeline,
                 default_model: Model = Model.SONNET) -> None:
        self._inner = inner
        self._pipeline = pipeline
        self._default_model = default_model

    def call(self, prompt, *, model="haiku", images=None):
        resp = self._inner.call(prompt, model=model, images=images)
        # Map model string → Model enum (default to SONNET).
        try:
            model_enum = Model(model)
        except ValueError:
            model_enum = self._default_model
        usage = TokenUsage(
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cached_input_tokens=getattr(resp, "cached_input_tokens", 0),
        )
        cost = estimate_cost(model_enum, usage)
        self._pipeline.record_cost(Phase.QA, cost)
        return resp


class QAOrchestrator:
    def __init__(self, agent: AgentCaller,
                 source_outlines: dict[str, list[str]] | None = None,
                 seed: int = 0) -> None:
        self._agent = agent
        self._source_outlines = source_outlines or {}
        self._seed = seed

    def run(self, vault: VaultPaths, pipeline: Pipeline,
            report_path: Path) -> QAReport:
        pipeline.mark_phase_started(Phase.QA)
        tracked_agent = _CostTrackingAgent(self._agent, pipeline)

        validators = [
            TranslationQualityValidator(agent=tracked_agent, seed=self._seed),
            LinkResolutionValidator(),
            CoverageValidator(agent=tracked_agent),
            CitationAccuracyValidator(agent=tracked_agent, seed=self._seed),
            ConceptCoherenceValidator(agent=tracked_agent, seed=self._seed),
            VaultIntegrityValidator(),
        ]

        results = []
        for v in validators:
            if isinstance(v, CoverageValidator):
                r = v.validate(vault=vault, source_outlines=self._source_outlines)
            else:
                r = v.validate(vault=vault)
            results.append(r)

        report = QAReport(
            overall_status=QAReport.compute_overall(results),
            validators=results,
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        pipeline.mark_phase_completed(Phase.QA)
        return report
