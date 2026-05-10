"""Passthrough converter for files that are already markdown."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import ConvertResult


HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class PassthroughConverter:
    """Returns the file content unchanged, with extracted heading outline."""

    def convert(self, path: Path) -> ConvertResult:
        content = path.read_text(encoding="utf-8")
        outline = [m.group(1) for m in HEADING_PATTERN.finditer(content)]
        meta = DocumentMeta(
            source_path=str(path),
            source_type="md",
            extraction_method=ExtractionMethod.PASSTHROUGH,
            page_count=1,
            extracted_chars=len(content),
            extracted_images_count=0,
            outline=outline,
            language_detected="und",
            ingested=datetime.now(timezone.utc).date(),
        )
        return ConvertResult(content=content, meta=meta)
