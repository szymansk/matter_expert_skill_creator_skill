def test_public_api_exports():
    """Verify the documented public API is reachable from the top-level package."""
    from matter_expert import (
        VaultPaths,
        ConceptPage, ConceptFrontmatter, Source,
        MOCPage, MOCFrontmatter,
        SourcePage, SourceFrontmatter,
        ConceptIndex, ConceptIndexEntry,
        MOCMap, MOCMapEntry,
        LinkGraph, LinkGraphEntry,
        AliasMap,
        validate_vault, validate_concept_frontmatter,
        ValidationIssue, Severity,
    )

    # Smoke check that they're the right types
    assert hasattr(VaultPaths, "concepts")
    assert hasattr(ConceptPage, "read")
    assert hasattr(LinkGraph, "build")
    assert hasattr(AliasMap, "build")
