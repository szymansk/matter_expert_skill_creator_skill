"""pandoc CLI wrapper — converts txt, html, docx, rtf, etc. to markdown."""
from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import ConvertResult


HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class PandocConverter:
    """Convert any pandoc-supported format to markdown via the pandoc CLI."""

    def convert(self, path: Path) -> ConvertResult:
        if shutil.which("pandoc") is None:
            raise RuntimeError("pandoc is required but not on PATH")

        proc = subprocess.run(
            ["pandoc", "-t", "gfm", str(path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"pandoc failed: {proc.stderr.strip()}")

        content = proc.stdout
        outline = [m.group(1) for m in HEADING_PATTERN.finditer(content)]
        suffix = path.suffix.lstrip(".").lower()

        meta = DocumentMeta(
            source_path=str(path),
            source_type=suffix,
            extraction_method=ExtractionMethod.PANDOC,
            page_count=1,
            extracted_chars=len(content),
            extracted_images_count=0,
            outline=outline,
            language_detected="und",
            ingested=datetime.now(timezone.utc).date(),
        )
        return ConvertResult(content=content, meta=meta)
