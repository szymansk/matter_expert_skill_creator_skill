def test_qa_public_api():
    from builder.qa import (
        OverallStatus, QAReport, Severity, ValidatorResult,
        TranslationQualityValidator, LinkResolutionValidator,
        CoverageValidator, CitationAccuracyValidator,
        ConceptCoherenceValidator, VaultIntegrityValidator,
        QAOrchestrator,
        SAMPLE_FRACTION_TRANSLATION,
    )
    assert SAMPLE_FRACTION_TRANSLATION == 0.05
