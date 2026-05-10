def test_ingest_public_api():
    from builder.ingest import (
        DocumentMeta, ExtractionMethod,
        AgentCaller, AgentResponse,
        Converter, ConvertResult,
        HTTPFetcher,
        PassthroughConverter, PandocConverter,
        PDFTextExtractor, PDFTextResult,
        DEFAULT_MIN_CHARS_PER_PAGE, is_text_extraction_plausible,
        VisionPDFConverter,
        URLFetchConverter,
        IngestOrchestrator,
    )
    assert DEFAULT_MIN_CHARS_PER_PAGE == 200
    assert callable(is_text_extraction_plausible)
