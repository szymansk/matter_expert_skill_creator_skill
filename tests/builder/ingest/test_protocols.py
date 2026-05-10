from datetime import date
from pathlib import Path

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import (
    AgentCaller,
    AgentResponse,
    ConvertResult,
    Converter,
    HTTPFetcher,
)


def test_convert_result_construction():
    meta = DocumentMeta(
        source_path="/x.md", source_type="md",
        extraction_method=ExtractionMethod.PASSTHROUGH,
        page_count=1, extracted_chars=10, extracted_images_count=0,
        outline=[], language_detected="en", ingested=date(2026, 5, 10),
    )
    result = ConvertResult(content="# Hello", meta=meta)
    assert result.content == "# Hello"
    assert result.meta.extraction_method == ExtractionMethod.PASSTHROUGH


def test_converter_protocol_check():
    """Anything implementing convert(path) -> ConvertResult is a Converter."""

    class FakeConv:
        def convert(self, path: Path) -> ConvertResult:
            return ConvertResult(content="x", meta=DocumentMeta(
                source_path=str(path), source_type="x",
                extraction_method=ExtractionMethod.PASSTHROUGH,
                page_count=1, extracted_chars=1, extracted_images_count=0,
                outline=[], language_detected="en", ingested=date(2026, 5, 10),
            ))

    fc = FakeConv()
    assert isinstance(fc, Converter)


def test_agent_response_construction():
    resp = AgentResponse(
        text="Some response text",
        input_tokens=100,
        output_tokens=50,
    )
    assert resp.text == "Some response text"
    assert resp.input_tokens == 100
    assert resp.output_tokens == 50
    assert resp.cached_input_tokens == 0


def test_agent_caller_protocol_check():
    class FakeAgent:
        def call(self, prompt: str, *, model: str = "haiku",
                 images: list[bytes] | None = None) -> AgentResponse:
            return AgentResponse(text="ok", input_tokens=1, output_tokens=1)

    assert isinstance(FakeAgent(), AgentCaller)


def test_http_fetcher_protocol_check():
    class FakeFetcher:
        def fetch(self, url: str) -> str:
            return "<html>body</html>"

    assert isinstance(FakeFetcher(), HTTPFetcher)
