"""End-to-end builder orchestrator chaining Ingest → Transform → Link → QA → Emit."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from builder.emit.orchestrator import EmitConfig, EmitOrchestrator
from builder.ingest.orchestrator import IngestOrchestrator
from builder.ingest.protocols import AgentCaller, HTTPFetcher
from builder.link.orchestrator import LinkOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline
from builder.qa.orchestrator import QAOrchestrator
from builder.transform.orchestrator import TransformOrchestrator
from matter_expert import VaultPaths


@dataclass
class BuildConfig:
    run_id: str
    input_dir: Path
    url_list: list[str]
    run_dir: Path
    plugin_root: Path
    plugin_name: str
    plugin_version: str
    plugin_description: str
    author: str
    replay_from: Phase | None = None


class BuilderOrchestrator:
    """End-to-end builder. Chains all 5 phases with Pipeline state mgmt."""

    def __init__(self, agent: AgentCaller, fetcher: HTTPFetcher) -> None:
        self._agent = agent
        self._fetcher = fetcher

    def build(self, config: BuildConfig) -> Pipeline:
        # Resume if state file exists; otherwise create.
        state_file = config.run_dir / "pipeline_state.json"
        if state_file.exists():
            pipeline = Pipeline.resume(config.run_dir)
        else:
            config.run_dir.mkdir(parents=True, exist_ok=True)
            pipeline = Pipeline.create(
                run_id=config.run_id,
                input_dir=config.input_dir,
                url_list=list(config.url_list),
                run_dir=config.run_dir,
            )

        if config.replay_from is not None:
            pipeline.replay_from(config.replay_from)

        # Working directories.
        work_root = config.run_dir / "work"
        work_root.mkdir(parents=True, exist_ok=True)
        vault_dir = work_root / "vault"
        ingest_state_file = work_root / "ingest_results.json"

        vault = VaultPaths(root=vault_dir)
        ingest_results = None

        # Phase 1: Ingest
        if not pipeline.is_phase_complete(Phase.INGEST):
            pipeline.mark_phase_started(Phase.INGEST)
            ingest = IngestOrchestrator(agent=self._agent, fetcher=self._fetcher)
            file_results = ingest.ingest_directory(
                directory=config.input_dir, pipeline=pipeline,
            )
            url_results = ingest.ingest_urls(
                urls=list(config.url_list), pipeline=pipeline,
            )
            ingest_results = {**file_results, **url_results}
            # Persist a lightweight summary of ingest results — what Transform needs.
            self._persist_ingest_summary(ingest_results, ingest_state_file)
            pipeline.mark_phase_completed(Phase.INGEST)
        elif ingest_state_file.exists():
            # Resume path: re-hydrate ingest_results from disk.
            ingest_results = self._load_ingest_summary(ingest_state_file)

        # Phase 2: Transform
        if not pipeline.is_phase_complete(Phase.TRANSFORM):
            if ingest_results is None:
                raise RuntimeError(
                    "transform phase cannot run: ingest results not available "
                    "(neither in-memory nor persisted)"
                )
            pipeline.mark_phase_started(Phase.TRANSFORM)
            transform = TransformOrchestrator(
                agent=self._agent, vault_dir=vault_dir,
            )
            transform.transform(
                ingest_results=ingest_results, pipeline=pipeline,
            )
            pipeline.mark_phase_completed(Phase.TRANSFORM)

        # Phase 3: Link
        if not pipeline.is_phase_complete(Phase.LINK):
            linker = LinkOrchestrator(agent=self._agent, vault_dir=vault_dir)
            linker.link(pipeline=pipeline)
            # link.link() already marks completed

        # Phase 4: QA
        if not pipeline.is_phase_complete(Phase.QA):
            qa_dir = work_root / "qa"
            qa = QAOrchestrator(agent=self._agent, source_outlines={})
            qa.run(
                vault=vault, pipeline=pipeline,
                report_path=qa_dir / "qa_report.json",
            )
            # qa.run() already marks completed

        # Phase 5: Emit
        if not pipeline.is_phase_complete(Phase.EMIT):
            emit_cfg = EmitConfig(
                plugin_name=config.plugin_name,
                plugin_version=config.plugin_version,
                plugin_description=config.plugin_description,
                author=config.author,
            )
            emitter = EmitOrchestrator(agent=self._agent, config=emit_cfg)
            emitter.emit(
                vault=vault, plugin_root=config.plugin_root,
                pipeline=pipeline,
            )

        return pipeline

    def _persist_ingest_summary(self, results: dict, path: Path) -> None:
        """Save ingest_results to disk so resume can re-hydrate."""
        path.parent.mkdir(parents=True, exist_ok=True)
        serializable = {
            source_id: {
                "content": r.content,
                "meta": r.meta.to_dict(),
            }
            for source_id, r in results.items()
        }
        path.write_text(
            json.dumps(serializable, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_ingest_summary(self, path: Path) -> dict:
        from builder.ingest.meta import DocumentMeta
        from builder.ingest.protocols import ConvertResult
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {
            sid: ConvertResult(
                content=item["content"],
                meta=DocumentMeta.from_dict(item["meta"]),
            )
            for sid, item in raw.items()
        }
