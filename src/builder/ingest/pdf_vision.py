"""Vision-based PDF extraction using a multimodal LLM via AgentCaller."""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import AgentCaller, ConvertResult


VISION_PROMPT = (
    "Extract the text content of this page as Markdown. Preserve headings, "
    "lists, tables, and emphasis. If the page contains a diagram or figure, "
    "describe it concisely as a markdown blockquote prefixed with FIGURE:."
)


class VisionPDFConverter:
    """Render each PDF page to PNG and ask the LLM to extract markdown."""

    def __init__(self, agent: AgentCaller, model: str = "sonnet") -> None:
        self._agent = agent
        self._model = model

    def convert(self, path: Path) -> ConvertResult:
        if shutil.which("pdftoppm") is None:
            raise RuntimeError("pdftoppm is required but not on PATH")

        page_chunks: list[str] = []
        total_input_tokens = 0
        total_output_tokens = 0

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            # Render each page as PNG.
            proc = subprocess.run(
                ["pdftoppm", "-r", "150", "-png", str(path), str(tmp_path / "page")],
                capture_output=True, text=True,
            )
            if proc.returncode != 0:
                raise RuntimeError(f"pdftoppm failed: {proc.stderr.strip()}")

            png_files = sorted(tmp_path.glob("page-*.png"))
            for png in png_files:
                image_bytes = png.read_bytes()
                resp = self._agent.call(
                    VISION_PROMPT,
                    model=self._model,
                    images=[image_bytes],
                )
                page_chunks.append(resp.text)
                total_input_tokens += resp.input_tokens
                total_output_tokens += resp.output_tokens

        page_count = len(page_chunks)
        content = "\n\n".join(page_chunks)

        meta = DocumentMeta(
            source_path=str(path),
            source_type="pdf",
            extraction_method=ExtractionMethod.VISION_FALLBACK,
            page_count=page_count,
            extracted_chars=len(content),
            extracted_images_count=page_count,
            outline=[],  # Could parse later; for now leave empty.
            language_detected="und",
            ingested=datetime.now(timezone.utc).date(),
        )
        return ConvertResult(content=content, meta=meta)
