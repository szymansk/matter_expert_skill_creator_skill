from datetime import datetime, timezone

from builder.ingest.meta import ExtractionMethod
from builder.ingest.url_fetch import URLFetchConverter


def test_url_fetch_returns_markdown(mock_fetcher):
    mock_fetcher.responses["https://example.com/spec"] = (
        "<h1>Hello</h1><p>Body text.</p>"
    )
    conv = URLFetchConverter(fetcher=mock_fetcher)

    result = conv.convert_url("https://example.com/spec")

    assert "Hello" in result.content
    assert result.meta.source_path == "https://example.com/spec"
    assert result.meta.source_type == "url"
    assert result.meta.extraction_method == ExtractionMethod.URL_FETCH
    assert mock_fetcher.calls == ["https://example.com/spec"]


def test_url_fetch_strips_html_to_text(mock_fetcher):
    mock_fetcher.responses["https://x"] = (
        "<html><head><title>T</title></head><body>"
        "<h2>Section</h2><p>Para 1.</p><p>Para 2.</p>"
        "</body></html>"
    )
    conv = URLFetchConverter(fetcher=mock_fetcher)

    result = conv.convert_url("https://x")
    # Headings preserved, paragraphs separated.
    assert "Section" in result.content
    assert "Para 1." in result.content
    assert "Para 2." in result.content


def test_url_fetch_outline_from_headings(mock_fetcher):
    mock_fetcher.responses["https://x"] = (
        "<html><body>"
        "<h1>Top</h1><h2>Sub</h2>"
        "<p>body</p>"
        "</body></html>"
    )
    conv = URLFetchConverter(fetcher=mock_fetcher)

    result = conv.convert_url("https://x")
    assert "Top" in result.meta.outline
    assert "Sub" in result.meta.outline
