"""Link phase — clusters, dedupes, assigns typed links, generates MOCs."""
from builder.link.cardinality import (
    MAX_RELATED,
    MAX_PREREQUISITES,
    MAX_EXAMPLES,
    MAX_CONTRASTS,
    MAX_REFINES,
    enforce_link_cardinality,
)
from builder.link.inventory import ConceptSummary, build_inventory
from builder.link.clusters import Cluster, ClusterError, ClusterIdentifier
from builder.link.merger import ConceptMerger
from builder.link.linker import LinkAgent, LinkError
from builder.link.moc_generator import MOCGenerator
from builder.link.orchestrator import LinkOrchestrator

__all__ = [
    "MAX_RELATED", "MAX_PREREQUISITES", "MAX_EXAMPLES",
    "MAX_CONTRASTS", "MAX_REFINES", "enforce_link_cardinality",
    "ConceptSummary", "build_inventory",
    "Cluster", "ClusterError", "ClusterIdentifier",
    "ConceptMerger",
    "LinkAgent", "LinkError",
    "MOCGenerator",
    "LinkOrchestrator",
]
