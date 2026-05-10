"""QA phase — 6 validators + aggregated QAReport."""
from builder.qa.report import (
    OverallStatus, QAReport, Severity, ValidatorResult,
)
from builder.qa.thresholds import (
    SAMPLE_FRACTION_TRANSLATION, SAMPLE_MIN_TRANSLATION,
    SAMPLE_FRACTION_CITATION, SAMPLE_FRACTION_COHERENCE,
    sample_items,
)
from builder.qa.translation import TranslationQualityValidator
from builder.qa.link_resolution import LinkResolutionValidator
from builder.qa.coverage import CoverageValidator
from builder.qa.citation import CitationAccuracyValidator
from builder.qa.coherence import ConceptCoherenceValidator
from builder.qa.integrity import VaultIntegrityValidator
from builder.qa.orchestrator import QAOrchestrator

__all__ = [
    "OverallStatus", "QAReport", "Severity", "ValidatorResult",
    "SAMPLE_FRACTION_TRANSLATION", "SAMPLE_MIN_TRANSLATION",
    "SAMPLE_FRACTION_CITATION", "SAMPLE_FRACTION_COHERENCE", "sample_items",
    "TranslationQualityValidator", "LinkResolutionValidator",
    "CoverageValidator", "CitationAccuracyValidator",
    "ConceptCoherenceValidator", "VaultIntegrityValidator",
    "QAOrchestrator",
]
