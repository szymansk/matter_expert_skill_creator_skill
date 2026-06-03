"""Ingest phase — converts source documents/URLs to markdown + metadata."""
from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import (
    AgentCaller,
    AgentResponse,
    Converter,
    ConvertResult,
    HTTPFetcher,
)
from builder.ingest.passthrough import PassthroughConverter
from builder.ingest.pandoc_converter import PandocConverter
from builder.ingest.pdf_text import (
    DEFAULT_MIN_CHARS_PER_PAGE,
    PDFTextExtractor,
    PDFTextResult,
    is_text_extraction_plausible,
)
from builder.ingest.pdf_vision import VisionPDFConverter
from builder.ingest.url_fetch import URLFetchConverter
from builder.ingest.orchestrator import IngestOrchestrator

__all__ = [
    "DocumentMeta", "ExtractionMethod",
    "AgentCaller", "AgentResponse",
    "Converter", "ConvertResult",
    "HTTPFetcher",
    "PassthroughConverter", "PandocConverter",
    "PDFTextExtractor", "PDFTextResult",
    "DEFAULT_MIN_CHARS_PER_PAGE", "is_text_extraction_plausible",
    "VisionPDFConverter",
    "URLFetchConverter",
    "IngestOrchestrator",
]
