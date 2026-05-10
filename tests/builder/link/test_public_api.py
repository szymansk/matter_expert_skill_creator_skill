def test_link_public_api():
    from builder.link import (
        MAX_RELATED, MAX_PREREQUISITES, MAX_EXAMPLES,
        MAX_CONTRASTS, MAX_REFINES, enforce_link_cardinality,
        ConceptSummary, build_inventory,
        Cluster, ClusterError, ClusterIdentifier,
        ConceptMerger,
        LinkAgent, LinkError,
        MOCGenerator,
        LinkOrchestrator,
    )
    assert MAX_RELATED == 8
    assert callable(enforce_link_cardinality)
