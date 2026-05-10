import shutil
from datetime import datetime, timezone

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pandoc_converter import PandocConverter


pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed",
)


def test_pandoc_converts_html(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "simple.html")

    assert "Heading One" in result.content
    assert result.meta.extraction_method == ExtractionMethod.PANDOC
    assert result.meta.source_type == "html"


def test_pandoc_converts_txt(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "plain.txt")

    assert "plain text document" in result.content.lower()
    assert result.meta.extraction_method == ExtractionMethod.PANDOC
    assert result.meta.source_type == "txt"


def test_pandoc_outline_from_html_headings(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "simple.html")

    assert "Heading One" in result.meta.outline
    assert "Heading Two" in result.meta.outline


def test_pandoc_extracted_chars_matches_content(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "plain.txt")
    assert result.meta.extracted_chars == len(result.content)


def test_pandoc_raises_when_missing(monkeypatch, ingest_fixtures_dir):
    monkeypatch.setattr("builder.ingest.pandoc_converter.shutil.which",
                        lambda _: None)
    conv = PandocConverter()
    with pytest.raises(RuntimeError, match="pandoc"):
        conv.convert(ingest_fixtures_dir / "plain.txt")
