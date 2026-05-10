"""pdftotext (Poppler) wrapper + plausibility heuristic."""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import ConvertResult


DEFAULT_MIN_CHARS_PER_PAGE = 200
HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class PDFTextResult:
    text: str
    page_count: int


def is_text_extraction_plausible(
    text: str,
    page_count: int,
    min_chars_per_page: int = DEFAULT_MIN_CHARS_PER_PAGE,
) -> bool:
    """Return True if the extracted text density looks plausible."""
    if page_count <= 0:
        return False
    if len(text) == 0:
        return False
    chars_per_page = len(text) / page_count
    return chars_per_page >= min_chars_per_page


class PDFTextExtractor:
    """Extract text from a PDF using pdftotext, with plausibility check."""

    def extract(self, path: Path) -> PDFTextResult:
        if shutil.which("pdftotext") is None:
            raise RuntimeError("pdftotext is required but not on PATH")

        proc = subprocess.run(
            ["pdftotext", str(path), "-"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pdftotext failed: {proc.stderr.strip()}")

        text = proc.stdout
        page_count = max(text.count("\f") + 1, 1)
        # Strip form-feed characters from the returned text
        text = text.replace("\f", "\n")
        return PDFTextResult(text=text, page_count=page_count)

    def convert(self, path: Path) -> ConvertResult:
        result = self.extract(path)
        outline = [m.group(1) for m in HEADING_PATTERN.finditer(result.text)]

        meta = DocumentMeta(
            source_path=str(path),
            source_type="pdf",
            extraction_method=ExtractionMethod.TEXT,
            page_count=result.page_count,
            extracted_chars=len(result.text),
            extracted_images_count=0,
            outline=outline,
            language_detected="und",
            ingested=datetime.now(timezone.utc).date(),
        )
        return ConvertResult(content=result.text, meta=meta)
