"""Transform orchestrator — runs analyzer → extractor → coverage per source doc."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.ingest.protocols import AgentCaller, ConvertResult
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.coverage import CoverageChecker
from builder.transform.extractor import ConceptExtractor
from matter_expert import (
    ConceptFrontmatter,
    ConceptPage,
    Source,
    SourceFrontmatter,
    SourcePage,
    VaultPaths,
)


class TransformOrchestrator:
    """Runs analyzer → extractor → coverage per ingest result; writes vault pages."""

    def __init__(self, agent: AgentCaller, vault_dir: Path) -> None:
        self._analyzer = ConceptAnalyzer(agent=agent)
        self._extractor = ConceptExtractor(agent=agent)
        self._coverage = CoverageChecker(agent=agent)
        self._vault_dir = vault_dir
        self._paths = VaultPaths(root=vault_dir)

    def transform(
        self,
        ingest_results: dict[str, ConvertResult],
        pipeline: Pipeline,
    ) -> dict[str, list[str]]:
        """Run transform on each ingest result.

        Returns map: source_id → list of concept names written.
        Records items and costs to Pipeline.
        """
        outputs: dict[str, list[str]] = {}
        # Ensure vault directories exist.
        self._paths.concepts.mkdir(parents=True, exist_ok=True)
        self._paths.sources.mkdir(parents=True, exist_ok=True)

        for source_id, convert_result in ingest_results.items():
            try:
                concepts = self._transform_one(source_id, convert_result, pipeline)
            except Exception as e:
                pipeline.record_item(
                    Phase.TRANSFORM, source_id,
                    status="failed", error=str(e),
                )
                continue
            outputs[source_id] = concepts
            pipeline.record_item(
                Phase.TRANSFORM, source_id,
                status="done",
                concepts_count=len(concepts),
            )
        return outputs

    def _transform_one(
        self,
        source_id: str,
        convert: ConvertResult,
        pipeline: Pipeline,
    ) -> list[str]:
        # 1. Analyze
        outline, usage = self._analyzer.analyze(
            source_text=convert.content,
            source_name=source_id,
        )
        self._record_cost(pipeline, usage)

        # 2. Write the source page
        self._write_source_page(source_id, convert)

        # 3. Extract each concept
        concept_names: list[str] = []
        extracted_titles: list[str] = []
        for entry in outline:
            body, ex_usage = self._extractor.extract(
                source_text=convert.content,
                source_name=source_id,
                concept_name=entry.concept_name,
                concept_title=entry.title,
            )
            self._record_cost(pipeline, ex_usage)
            self._write_concept_page(entry, body, convert, source_id)
            concept_names.append(entry.concept_name)
            extracted_titles.append(entry.title)

        # 4. Coverage check
        _missed, cov_usage = self._coverage.check(
            source_outline=convert.meta.outline,
            extracted_titles=extracted_titles,
        )
        self._record_cost(pipeline, cov_usage)
        return concept_names

    def _record_cost(self, pipeline: Pipeline, usage) -> None:
        """`usage` is an AgentResponse — convert to TokenUsage + record."""
        token_usage = TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=getattr(usage, "cached_input_tokens", 0),
        )
        cost = estimate_cost(Model.HAIKU, token_usage)
        pipeline.record_cost(Phase.TRANSFORM, cost)

    def _write_concept_page(
        self,
        entry,
        body: str,
        convert: ConvertResult,
        source_id: str,
    ) -> None:
        fm = ConceptFrontmatter(
            title=entry.title,
            sources=[Source(file=source_id, sections=list(entry.source_sections))],
            tags=[],
            created=datetime.now(timezone.utc).date(),
        )
        page = ConceptPage(
            frontmatter=fm,
            body=body,
            path=self._paths.concept_for(entry.concept_name),
        )
        page.write()

    def _write_source_page(self, source_id: str, convert: ConvertResult) -> None:
        """Mirror the original ingest output under vault/sources/."""
        stem = Path(source_id).stem
        # Map ingest extraction_method to source page's extraction_method literal
        method = convert.meta.extraction_method.value
        # Some methods aren't part of SourceFrontmatter's Literal — coerce.
        if method not in {"text", "vision_fallback", "hybrid"}:
            method = "text"
        fm = SourceFrontmatter(
            title=stem,
            original_file=convert.meta.source_path,
            original_format=convert.meta.source_type,
            page_count=convert.meta.page_count,
            extraction_method=method,  # type: ignore[arg-type]
            language_detected=convert.meta.language_detected,
            ingested=convert.meta.ingested,
        )
        page = SourcePage(
            frontmatter=fm,
            body=convert.content,
            path=self._paths.source_for(stem),
        )
        page.write()
