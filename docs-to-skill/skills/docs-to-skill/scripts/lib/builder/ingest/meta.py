"""Document extraction metadata produced by the Ingest phase."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any


class ExtractionMethod(Enum):
    """How the source document was converted to markdown."""
    TEXT = "text"                   # PDF text extraction succeeded
    VISION_FALLBACK = "vision_fallback"  # PDF needed vision (LLM)
    HYBRID = "hybrid"               # Mixed text + vision (some pages each)
    PASSTHROUGH = "passthrough"     # Was already markdown
    PANDOC = "pandoc"               # Converted via pandoc
    URL_FETCH = "url_fetch"         # Fetched from URL


@dataclass
class DocumentMeta:
    """Metadata about a single converted source document."""
    source_path: str           # File path or URL
    source_type: str           # "pdf" | "docx" | "html" | "md" | "txt" | "url" | ...
    extraction_method: ExtractionMethod
    page_count: int
    extracted_chars: int
    extracted_images_count: int
    outline: list[str]         # Top-level headings extracted
    language_detected: str     # ISO 639-1 code, or "und" for undetermined
    ingested: date

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DocumentMeta":
        return cls(
            source_path=data["source_path"],
            source_type=data["source_type"],
            extraction_method=ExtractionMethod(data["extraction_method"]),
            page_count=int(data["page_count"]),
            extracted_chars=int(data["extracted_chars"]),
            extracted_images_count=int(data.get("extracted_images_count", 0)),
            outline=list(data.get("outline", [])),
            language_detected=data["language_detected"],
            ingested=date.fromisoformat(data["ingested"])
                if isinstance(data["ingested"], str)
                else data["ingested"],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_type": self.source_type,
            "extraction_method": self.extraction_method.value,
            "page_count": self.page_count,
            "extracted_chars": self.extracted_chars,
            "extracted_images_count": self.extracted_images_count,
            "outline": list(self.outline),
            "language_detected": self.language_detected,
            "ingested": self.ingested.isoformat(),
        }
