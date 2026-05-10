"""Emit orchestrator — produces the final installable plugin."""
from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.emit.index_builder import build_indexes
from builder.emit.memory_initializer import initialize_memory
from builder.emit.plugin_metadata import PluginMetadata, write_plugin_json
from builder.emit.readme import ReadmeMeta, generate_readme
from builder.emit.runtime_bundler import bundle_runtime
from builder.emit.skill_md import SkillMdMeta, generate_skill_md
from builder.ingest.protocols import AgentCaller
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from matter_expert import VaultPaths


@dataclass(frozen=True)
class EmitConfig:
    plugin_name: str
    plugin_version: str
    plugin_description: str
    author: str


class _CostTrackingAgent:
    def __init__(self, inner: AgentCaller, pipeline: Pipeline) -> None:
        self._inner = inner
        self._pipeline = pipeline

    def call(self, prompt, *, model="haiku", images=None):
        resp = self._inner.call(prompt, model=model, images=images)
        try:
            model_enum = Model(model)
        except ValueError:
            model_enum = Model.SONNET
        usage = TokenUsage(
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cached_input_tokens=getattr(resp, "cached_input_tokens", 0),
        )
        self._pipeline.record_cost(Phase.EMIT,
                                    estimate_cost(model_enum, usage))
        return resp


class EmitOrchestrator:
    def __init__(self, agent: AgentCaller, config: EmitConfig) -> None:
        self._agent = agent
        self._config = config

    def emit(self, vault: VaultPaths, plugin_root: Path,
             pipeline: Pipeline) -> None:
        pipeline.mark_phase_started(Phase.EMIT)
        tracked = _CostTrackingAgent(self._agent, pipeline)

        cfg = self._config
        skill_dir = plugin_root / "skills" / cfg.plugin_name
        bundled_vault = skill_dir / "vault"
        index_dir = skill_dir / "_index"
        memory_dir = skill_dir / "memory"

        # 1. Copy the vault into the plugin.
        self._copy_vault(vault, bundled_vault)

        # 2. Build the 4 indexes from the bundled vault.
        bundled_paths = VaultPaths(root=bundled_vault)
        build_indexes(vault=bundled_paths, index_dir=index_dir)

        # 3. Bundle the runtime scripts.
        bundle_runtime(plugin_skill_dir=skill_dir)

        # 4. Generate SKILL.md (LLM call → cost recorded via tracked agent).
        topics = self._extract_dominant_topics(bundled_paths)
        generate_skill_md(
            skill_dir=skill_dir,
            meta=SkillMdMeta(skill_name=cfg.plugin_name, dominant_topics=topics),
            agent=tracked,
        )

        # 5. Initialize memory.
        link_graph = json.loads(
            (index_dir / "link_graph.json").read_text(encoding="utf-8")
        )
        initialize_memory(memory_dir=memory_dir, link_graph=link_graph)

        # 6. Write plugin.json.
        write_plugin_json(
            PluginMetadata(
                name=cfg.plugin_name, version=cfg.plugin_version,
                description=cfg.plugin_description, author=cfg.author,
            ),
            plugin_root=plugin_root,
        )

        # 7. Write README.
        concept_count = (
            len(list(bundled_paths.concepts.glob("*.md")))
            if bundled_paths.concepts.exists() else 0
        )
        moc_count = (
            len(list(bundled_paths.mocs.glob("*.md")))
            if bundled_paths.mocs.exists() else 0
        )
        generate_readme(
            plugin_root=plugin_root,
            meta=ReadmeMeta(
                plugin_name=cfg.plugin_name, version=cfg.plugin_version,
                description=cfg.plugin_description,
                concept_count=concept_count, moc_count=moc_count,
            ),
        )

        pipeline.mark_phase_completed(Phase.EMIT)

    def _copy_vault(self, vault: VaultPaths, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)
        for subdir in ("concepts", "MOCs", "sources"):
            src = vault.root / subdir
            if src.exists():
                shutil.copytree(src, dest / subdir, dirs_exist_ok=True)

    def _extract_dominant_topics(self, vault: VaultPaths) -> list[str]:
        """Return the top tags across all concepts (most frequent first)."""
        from collections import Counter
        from matter_expert import ConceptPage
        counts: Counter[str] = Counter()
        if vault.concepts.exists():
            for path in vault.concepts.glob("*.md"):
                page = ConceptPage.read(path)
                counts.update(page.frontmatter.tags)
        return [tag for tag, _ in counts.most_common(10)]
