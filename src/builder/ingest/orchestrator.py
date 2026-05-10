"""Ingest orchestrator — dispatches per-file converters and records progress."""
from __future__ import annotations

from pathlib import Path

from builder.ingest.pandoc_converter import PandocConverter
from builder.ingest.passthrough import PassthroughConverter
from builder.ingest.pdf_text import PDFTextExtractor, is_text_extraction_plausible
from builder.ingest.pdf_vision import VisionPDFConverter
from builder.ingest.protocols import AgentCaller, ConvertResult, HTTPFetcher
from builder.ingest.url_fetch import URLFetchConverter
from builder.phases import Phase
from builder.pipeline import Pipeline


PANDOC_EXTENSIONS = {".txt", ".html", ".htm", ".docx", ".rtf", ".odt", ".epub"}
MD_EXTENSIONS = {".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}


class IngestOrchestrator:
    """Dispatches input files/URLs to the right converter; records to Pipeline."""

    def __init__(self, agent: AgentCaller, fetcher: HTTPFetcher) -> None:
        self._passthrough = PassthroughConverter()
        self._pandoc = PandocConverter()
        self._pdf_text = PDFTextExtractor()
        self._pdf_vision = VisionPDFConverter(agent=agent)
        self._url_fetch = URLFetchConverter(fetcher=fetcher)

    def ingest_directory(
        self,
        directory: Path,
        pipeline: Pipeline,
        only_files: list[str] | None = None,
    ) -> dict[str, ConvertResult]:
        """Convert every file in `directory` (or only the listed names)."""
        results: dict[str, ConvertResult] = {}
        files = [
            p for p in sorted(directory.iterdir())
            if p.is_file() and (only_files is None or p.name in only_files)
        ]
        for path in files:
            item_id = path.name
            try:
                result = self._convert_file(path)
            except Exception as e:
                pipeline.record_item(
                    Phase.INGEST, item_id, status="failed", error=str(e),
                )
                continue
            results[item_id] = result
            pipeline.record_item(
                Phase.INGEST, item_id,
                status="done",
                extraction_method=result.meta.extraction_method.value,
                page_count=result.meta.page_count,
                extracted_chars=result.meta.extracted_chars,
            )
        return results

    def ingest_urls(
        self,
        urls: list[str],
        pipeline: Pipeline,
    ) -> dict[str, ConvertResult]:
        results: dict[str, ConvertResult] = {}
        for url in urls:
            try:
                result = self._url_fetch.convert_url(url)
            except Exception as e:
                pipeline.record_item(
                    Phase.INGEST, url, status="failed", error=str(e),
                )
                continue
            results[url] = result
            pipeline.record_item(
                Phase.INGEST, url,
                status="done",
                extraction_method=result.meta.extraction_method.value,
                extracted_chars=result.meta.extracted_chars,
            )
        return results

    def _convert_file(self, path: Path) -> ConvertResult:
        ext = path.suffix.lower()
        if ext in MD_EXTENSIONS:
            return self._passthrough.convert(path)
        if ext in PANDOC_EXTENSIONS:
            return self._pandoc.convert(path)
        if ext in PDF_EXTENSIONS:
            return self._convert_pdf(path)
        raise ValueError(f"unsupported extension: {ext}")

    def _convert_pdf(self, path: Path) -> ConvertResult:
        # Try text extraction first.
        text_result = self._pdf_text.extract(path)
        if is_text_extraction_plausible(text_result.text, text_result.page_count):
            return self._pdf_text.convert(path)
        # Fall back to vision.
        return self._pdf_vision.convert(path)
