import shutil

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pdf_text import (
    DEFAULT_MIN_CHARS_PER_PAGE,
    PDFTextExtractor,
    PDFTextResult,
    is_text_extraction_plausible,
)


pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext not installed",
)


def test_pdftext_extracts_content(ingest_fixtures_dir):
    ext = PDFTextExtractor()
    result = ext.extract(ingest_fixtures_dir / "tiny.pdf")

    assert isinstance(result, PDFTextResult)
    assert result.page_count >= 1
    assert len(result.text) > 0
    assert "body content" in result.text.lower() or "sample" in result.text.lower()


def test_plausibility_check_passes_for_normal_text():
    """A typical text page (200+ chars) is plausible."""
    sample = "x" * 250
    assert is_text_extraction_plausible(sample, page_count=1) is True


def test_plausibility_check_fails_for_empty():
    assert is_text_extraction_plausible("", page_count=10) is False


def test_plausibility_check_fails_below_min_chars_per_page():
    sample = "tiny"  # 4 chars
    # 4/10 = 0.4 chars/page, way below default 200
    assert is_text_extraction_plausible(sample, page_count=10) is False


def test_plausibility_threshold_configurable():
    sample = "x" * 100
    # At default 200 chars/page on 1 page → fails
    assert is_text_extraction_plausible(sample, page_count=1) is False
    # At threshold 50 → passes
    assert is_text_extraction_plausible(sample, page_count=1,
                                          min_chars_per_page=50) is True


def test_default_threshold_constant():
    assert DEFAULT_MIN_CHARS_PER_PAGE == 200


def test_extractor_produces_convert_result(ingest_fixtures_dir):
    """Higher-level interface: convert() returns a ConvertResult with TEXT method
    when extraction is plausible."""
    ext = PDFTextExtractor()
    result = ext.convert(ingest_fixtures_dir / "tiny.pdf")
    assert result.meta.extraction_method == ExtractionMethod.TEXT
    assert result.meta.source_type == "pdf"
    assert result.meta.extracted_chars == len(result.content)


def test_extractor_raises_when_pdftotext_missing(monkeypatch, ingest_fixtures_dir):
    monkeypatch.setattr("builder.ingest.pdf_text.shutil.which",
                        lambda _: None)
    ext = PDFTextExtractor()
    with pytest.raises(RuntimeError, match="pdftotext"):
        ext.extract(ingest_fixtures_dir / "tiny.pdf")


def test_convert_from_extracted_matches_convert(ingest_fixtures_dir):
    """convert_from_extracted() with a pre-run result must equal convert()."""
    ext = PDFTextExtractor()
    path = ingest_fixtures_dir / "tiny.pdf"
    pre = ext.extract(path)
    from_extracted = ext.convert_from_extracted(path, pre)
    direct = ext.convert(path)

    assert from_extracted.content == direct.content
    assert from_extracted.meta.extraction_method == direct.meta.extraction_method
    assert from_extracted.meta.page_count == direct.meta.page_count
    assert from_extracted.meta.extracted_chars == direct.meta.extracted_chars
