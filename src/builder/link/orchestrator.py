"""Link orchestrator — clustering → merging → typed link assignment → MOCs."""
from __future__ import annotations

from pathlib import Path

from builder.cost_tracker import TokenUsage, estimate_cost
from builder.ingest.protocols import AgentCaller
from builder.link.clusters import ClusterIdentifier
from builder.link.inventory import build_inventory
from builder.link.linker import LinkAgent
from builder.link.merger import ConceptMerger
from builder.link.moc_generator import MOCGenerator
from builder.phases import Model, Phase
from builder.pipeline import Pipeline
from matter_expert import ConceptPage, Source, VaultPaths


class LinkOrchestrator:
    """Runs the full Link phase across vault/concepts/."""

    def __init__(self, agent: AgentCaller, vault_dir: Path) -> None:
        self._clusters = ClusterIdentifier(agent=agent)
        self._merger = ConceptMerger(agent=agent)
        self._linker = LinkAgent(agent=agent)
        self._mocs = MOCGenerator()
        self._paths = VaultPaths(root=vault_dir)

    def link(self, pipeline: Pipeline) -> None:
        pipeline.mark_phase_started(Phase.LINK)

        # 1. Build inventory from current vault state.
        inventory = build_inventory(self._paths.concepts)
        if not inventory:
            pipeline.mark_phase_completed(Phase.LINK)
            return

        # 2. Identify clusters of duplicate concepts.
        clusters, usage = self._clusters.identify(inventory)
        self._record_cost(pipeline, usage)

        # 3. Merge each cluster.
        for cluster in clusters:
            self._merge_cluster(cluster, pipeline)

        # 4. Rebuild inventory after merges.
        inventory = build_inventory(self._paths.concepts)

        # 5. Assign typed links to each surviving concept.
        for summary in inventory:
            self._assign_links(summary, inventory, pipeline)

        # 6. Generate MOCs from final inventory.
        self._mocs.generate(inventory, self._paths.mocs)

        pipeline.mark_phase_completed(Phase.LINK)

    def _merge_cluster(self, cluster, pipeline: Pipeline) -> None:
        """Merge a cluster into the first member's filename."""
        member_pages: list[ConceptPage] = []
        for name in cluster.members:
            path = self._paths.concept_for(name)
            if path.exists():
                member_pages.append(ConceptPage.read(path))
        if len(member_pages) < 2:
            return

        merge_input = [
            {"name": p.name, "title": p.frontmatter.title, "body": p.body,
             "sources": [s.to_dict() for s in p.frontmatter.sources]}
            for p in member_pages
        ]
        merged, usage = self._merger.merge(merge_input)
        self._record_cost(pipeline, usage)

        # Survivor = first member's page (preserves canonical name).
        survivor = member_pages[0]
        new_sources = [
            Source(file=s["file"], sections=list(s.get("sections", [])))
            for s in merged["sources"]
        ]
        survivor.frontmatter.sources = new_sources
        survivor.frontmatter.merged_from = list(merged["merged_from"])
        survivor.body = merged["body"]
        survivor.write()

        # Delete all other members.
        for p in member_pages[1:]:
            p.path.unlink()
            pipeline.record_item(
                Phase.LINK, p.name, status="done",
                action="merged_into", into=survivor.name,
            )

    def _assign_links(
        self,
        target,
        inventory: list,
        pipeline: Pipeline,
    ) -> None:
        links, usage = self._linker.assign(target, inventory)
        self._record_cost(pipeline, usage)

        path = self._paths.concept_for(target.name)
        page = ConceptPage.read(path)
        page.frontmatter.related = list(links["related"])
        page.frontmatter.prerequisites = list(links["prerequisites"])
        page.frontmatter.examples = list(links["examples"])
        page.frontmatter.contrasts = list(links["contrasts"])
        page.frontmatter.refines = list(links["refines"])
        page.write()
        pipeline.record_item(Phase.LINK, target.name, status="done")

    def _record_cost(self, pipeline: Pipeline, usage) -> None:
        token_usage = TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=getattr(usage, "cached_input_tokens", 0),
        )
        cost = estimate_cost(Model.SONNET, token_usage)
        pipeline.record_cost(Phase.LINK, cost)
