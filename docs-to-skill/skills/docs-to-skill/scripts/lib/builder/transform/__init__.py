"""Transform phase — translates and chunks raw markdown into vault pages."""
from builder.transform.outline import ConceptOutline, OutlineEntry
from builder.transform.chunk_size import (
    MIN_CHUNK_TOKENS,
    MAX_CHUNK_TOKENS,
    classify_chunk_size,
    estimate_tokens,
)
from builder.transform.analyzer import AnalyzerError, ConceptAnalyzer
from builder.transform.extractor import ConceptExtractor
from builder.transform.coverage import CoverageChecker, CoverageError
from builder.transform.orchestrator import TransformOrchestrator

__all__ = [
    "ConceptOutline", "OutlineEntry",
    "MIN_CHUNK_TOKENS", "MAX_CHUNK_TOKENS",
    "classify_chunk_size", "estimate_tokens",
    "AnalyzerError", "ConceptAnalyzer",
    "ConceptExtractor",
    "CoverageChecker", "CoverageError",
    "TransformOrchestrator",
]
