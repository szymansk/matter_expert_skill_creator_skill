from datetime import date, timezone
import datetime as dt

from builder.ingest.meta import ExtractionMethod
from builder.ingest.passthrough import PassthroughConverter


def test_passthrough_returns_raw_markdown(ingest_fixtures_dir):
    converter = PassthroughConverter()
    result = converter.convert(ingest_fixtures_dir / "plain.md")

    assert "# Plain Markdown" in result.content
    assert "**bold**" in result.content


def test_passthrough_meta_set_correctly(ingest_fixtures_dir):
    converter = PassthroughConverter()
    result = converter.convert(ingest_fixtures_dir / "plain.md")

    assert result.meta.source_type == "md"
    assert result.meta.extraction_method == ExtractionMethod.PASSTHROUGH
    assert result.meta.page_count == 1
    assert result.meta.extracted_chars == len(result.content)
    assert result.meta.extracted_images_count == 0
    assert result.meta.ingested == dt.datetime.now(timezone.utc).date()


def test_passthrough_outline_extracted_from_headings(ingest_fixtures_dir):
    converter = PassthroughConverter()
    result = converter.convert(ingest_fixtures_dir / "plain.md")

    assert "Plain Markdown" in result.meta.outline
    assert "Section" in result.meta.outline
