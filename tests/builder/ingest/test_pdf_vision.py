import shutil

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pdf_vision import VisionPDFConverter


pytestmark = pytest.mark.skipif(
    shutil.which("pdftoppm") is None,
    reason="pdftoppm not installed",
)


def test_vision_converter_calls_agent_per_page(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    result = conv.convert(ingest_fixtures_dir / "tiny.pdf")

    # At least one agent call (one per page).
    assert len(mock_agent.calls) >= 1
    # Each call carries images.
    for call in mock_agent.calls:
        assert call["n_images"] == 1


def test_vision_converter_uses_sonnet_by_default(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    conv.convert(ingest_fixtures_dir / "tiny.pdf")
    for call in mock_agent.calls:
        assert call["model"] == "sonnet"


def test_vision_converter_meta(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    result = conv.convert(ingest_fixtures_dir / "tiny.pdf")

    assert result.meta.source_type == "pdf"
    assert result.meta.extraction_method == ExtractionMethod.VISION_FALLBACK
    assert result.meta.page_count >= 1
    # Body assembled from agent responses.
    assert "MOCK_AGENT_RESPONSE" in result.content


def test_vision_converter_surfaces_token_usage(ingest_fixtures_dir, mock_agent):
    """ConvertResult.token_usage must carry the total tokens across all pages."""
    conv = VisionPDFConverter(agent=mock_agent)
    result = conv.convert(ingest_fixtures_dir / "tiny.pdf")

    assert result.token_usage is not None
    n_pages = len(mock_agent.calls)
    assert result.token_usage.input_tokens == mock_agent.canned_input_tokens * n_pages
    assert result.token_usage.output_tokens == mock_agent.canned_output_tokens * n_pages
