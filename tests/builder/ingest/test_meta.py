from datetime import date

from builder.ingest.meta import DocumentMeta, ExtractionMethod


def test_extraction_method_values():
    assert ExtractionMethod.TEXT.value == "text"
    assert ExtractionMethod.VISION_FALLBACK.value == "vision_fallback"
    assert ExtractionMethod.HYBRID.value == "hybrid"
    assert ExtractionMethod.PASSTHROUGH.value == "passthrough"
    assert ExtractionMethod.PANDOC.value == "pandoc"
    assert ExtractionMethod.URL_FETCH.value == "url_fetch"


def test_document_meta_construction():
    meta = DocumentMeta(
        source_path="/inputs/handbook.pdf",
        source_type="pdf",
        extraction_method=ExtractionMethod.TEXT,
        page_count=240,
        extracted_chars=187000,
        extracted_images_count=23,
        outline=["1. Intro", "1.1 Grundlagen"],
        language_detected="de",
        ingested=date(2026, 5, 10),
    )
    assert meta.source_path == "/inputs/handbook.pdf"
    assert meta.extraction_method == ExtractionMethod.TEXT


def test_document_meta_round_trip():
    meta = DocumentMeta(
        source_path="/x.pdf",
        source_type="pdf",
        extraction_method=ExtractionMethod.VISION_FALLBACK,
        page_count=10,
        extracted_chars=5000,
        extracted_images_count=0,
        outline=[],
        language_detected="en",
        ingested=date(2026, 5, 10),
    )
    assert DocumentMeta.from_dict(meta.to_dict()) == meta


def test_document_meta_url_source():
    """For URL inputs, source_path is the URL."""
    meta = DocumentMeta(
        source_path="https://example.com/doc",
        source_type="url",
        extraction_method=ExtractionMethod.URL_FETCH,
        page_count=1,
        extracted_chars=2000,
        extracted_images_count=0,
        outline=[],
        language_detected="en",
        ingested=date(2026, 5, 10),
    )
    assert meta.source_type == "url"
