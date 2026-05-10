def test_transform_public_api():
    from builder.transform import (
        ConceptOutline, OutlineEntry,
        MIN_CHUNK_TOKENS, MAX_CHUNK_TOKENS,
        classify_chunk_size, estimate_tokens,
        AnalyzerError, ConceptAnalyzer,
        ConceptExtractor,
        CoverageChecker, CoverageError,
        TransformOrchestrator,
    )
    assert MIN_CHUNK_TOKENS == 500
    assert callable(classify_chunk_size)
