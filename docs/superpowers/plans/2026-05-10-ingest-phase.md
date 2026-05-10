# Ingest Phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Ingest phase of the docs-to-skill builder — converts heterogeneous source documents (PDF, DOCX, HTML, MD, TXT) and URLs into raw markdown plus extraction metadata, with vision fallback for layout-heavy PDFs.

**Architecture:** Inside `src/builder/ingest/`. Pure-Python orchestration delegates to converter protocols (`Converter`, `AgentCaller`, `HTTPFetcher`) that are mocked in tests and have real implementations using pandoc, pdftotext, the Anthropic SDK, and HTTP requests. Plausibility heuristic (chars/page) decides whether PDF text extraction is good enough or vision fallback is needed.

**Tech Stack:** Python 3.11+ stdlib + system binaries (pandoc, pdftotext, pdftoppm). Tests use small fixture documents committed under `tests/fixtures/ingest_samples/`.

---

## File Structure

```
src/builder/ingest/
├── __init__.py
├── meta.py              # DocumentMeta dataclass + extraction method enum
├── protocols.py         # Converter, AgentCaller, HTTPFetcher abstract bases
├── passthrough.py       # PassthroughConverter (.md → as-is)
├── pandoc_converter.py  # pandoc CLI wrapper (txt, docx, html, rtf)
├── pdf_text.py          # pdftotext + plausibility check
├── pdf_vision.py        # Vision-based PDF extraction via AgentCaller
├── url_fetch.py         # URL fetcher via HTTPFetcher → markdown
└── orchestrator.py      # Ingest function: dispatches by extension/URL,
                         #    integrates with Pipeline (record_item/cost)

tests/builder/ingest/
├── __init__.py
├── conftest.py          # mock AgentCaller, mock HTTPFetcher, fixture paths
├── fixtures/
│   ├── plain.txt
│   ├── plain.md
│   ├── simple.html
│   └── tiny.pdf         # text-extractable
├── test_meta.py
├── test_passthrough.py
├── test_pandoc_converter.py
├── test_pdf_text.py
├── test_pdf_vision.py
├── test_url_fetch.py
└── test_orchestrator.py
```

---

## Task 1: Ingest Package + DocumentMeta + Smoke

**Files:**
- Create: `src/builder/ingest/__init__.py`
- Create: `src/builder/ingest/meta.py`
- Create: `tests/builder/ingest/__init__.py`
- Create: `tests/builder/ingest/test_meta.py`

- [ ] **Step 1: Create `src/builder/ingest/__init__.py`** (empty for now)

- [ ] **Step 2: Create `tests/builder/ingest/__init__.py`** (empty)

- [ ] **Step 3: Write failing test `tests/builder/ingest/test_meta.py`**

```python
from datetime import date

from builder.ingest.meta import DocumentMeta, ExtractionMethod


def test_extraction_method_values():
    assert ExtractionMethod.TEXT.value == "text"
    assert ExtractionMethod.VISION_FALLBACK.value == "vision_fallback"
    assert ExtractionMethod.HYBRID.value == "hybrid"
    assert ExtractionMethod.PASSTHROUGH.value == "passthrough"
    assert ExtractionMethod.PANDOC.value == "pandoc"
    assert ExtractionMethod.URL_FETCH.value == "url_fetch"


def test_document_meta_construction():
    meta = DocumentMeta(
        source_path="/inputs/handbook.pdf",
        source_type="pdf",
        extraction_method=ExtractionMethod.TEXT,
        page_count=240,
        extracted_chars=187000,
        extracted_images_count=23,
        outline=["1. Intro", "1.1 Grundlagen"],
        language_detected="de",
        ingested=date(2026, 5, 10),
    )
    assert meta.source_path == "/inputs/handbook.pdf"
    assert meta.extraction_method == ExtractionMethod.TEXT


def test_document_meta_round_trip():
    meta = DocumentMeta(
        source_path="/x.pdf",
        source_type="pdf",
        extraction_method=ExtractionMethod.VISION_FALLBACK,
        page_count=10,
        extracted_chars=5000,
        extracted_images_count=0,
        outline=[],
        language_detected="en",
        ingested=date(2026, 5, 10),
    )
    assert DocumentMeta.from_dict(meta.to_dict()) == meta


def test_document_meta_url_source():
    """For URL inputs, source_path is the URL."""
    meta = DocumentMeta(
        source_path="https://example.com/doc",
        source_type="url",
        extraction_method=ExtractionMethod.URL_FETCH,
        page_count=1,
        extracted_chars=2000,
        extracted_images_count=0,
        outline=[],
        language_detected="en",
        ingested=date(2026, 5, 10),
    )
    assert meta.source_type == "url"
```

- [ ] **Step 4: Run → fail with ImportError**

- [ ] **Step 5: Implement `src/builder/ingest/meta.py`**

```python
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
```

- [ ] **Step 6: Run → 4 tests pass**

- [ ] **Step 7: Commit**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
git add src/builder/ingest/ tests/builder/ingest/
git commit -m "feat(builder/ingest): DocumentMeta + ExtractionMethod"
```

---

## Task 2: Converter / AgentCaller / HTTPFetcher Protocols

**Files:**
- Create: `src/builder/ingest/protocols.py`
- Create: `tests/builder/ingest/test_protocols.py`

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_protocols.py`**

```python
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
```

- [ ] **Step 2: Run → fail with ImportError**

- [ ] **Step 3: Implement `src/builder/ingest/protocols.py`**

```python
"""Protocols for Ingest-phase pluggable behaviour.

Tests pass mock objects implementing these structural types; production
wires real implementations (pandoc subprocess, Anthropic SDK, HTTP client).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from builder.ingest.meta import DocumentMeta


@dataclass(frozen=True)
class ConvertResult:
    """Output of a Converter — markdown body + extraction metadata."""
    content: str
    meta: DocumentMeta


@dataclass(frozen=True)
class AgentResponse:
    """LLM response for an agent call (used by vision fallback, etc.)."""
    text: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


@runtime_checkable
class Converter(Protocol):
    """Converts a source file to markdown + metadata."""

    def convert(self, path: Path) -> ConvertResult:
        ...


@runtime_checkable
class AgentCaller(Protocol):
    """Calls an LLM with a prompt and optional images."""

    def call(
        self,
        prompt: str,
        *,
        model: str = "haiku",
        images: list[bytes] | None = None,
    ) -> AgentResponse:
        ...


@runtime_checkable
class HTTPFetcher(Protocol):
    """Fetches the body of a URL as a string."""

    def fetch(self, url: str) -> str:
        ...
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/protocols.py tests/builder/ingest/test_protocols.py
git commit -m "feat(builder/ingest): Converter/AgentCaller/HTTPFetcher protocols"
```

---

## Task 3: Conftest with Sample Fixtures + Mocks

**Files:**
- Create: `tests/builder/ingest/conftest.py`
- Create: `tests/builder/ingest/fixtures/plain.txt`
- Create: `tests/builder/ingest/fixtures/plain.md`
- Create: `tests/builder/ingest/fixtures/simple.html`

- [ ] **Step 1: Create fixture text file `tests/builder/ingest/fixtures/plain.txt`**

```
A plain text document.

It has multiple paragraphs.
Some sentences span lines.

That's all.
```

- [ ] **Step 2: Create fixture markdown file `tests/builder/ingest/fixtures/plain.md`**

```markdown
# Plain Markdown

This is a markdown document with **bold** and *italic* text.

## Section

A paragraph here.
```

- [ ] **Step 3: Create fixture HTML file `tests/builder/ingest/fixtures/simple.html`**

```html
<!DOCTYPE html>
<html>
<head><title>Simple</title></head>
<body>
<h1>Heading One</h1>
<p>A paragraph with <strong>bold</strong> and <em>italic</em>.</p>
<h2>Heading Two</h2>
<p>Another paragraph.</p>
</body>
</html>
```

- [ ] **Step 4: Create `tests/builder/ingest/conftest.py`**

```python
"""Shared fixtures for ingest tests.

- `ingest_fixtures_dir`: path to checked-in sample files
- `mock_agent`: a stub AgentCaller capturing prompts and returning canned responses
- `mock_fetcher`: a stub HTTPFetcher returning canned bodies per URL
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest

from builder.ingest.protocols import AgentResponse


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def ingest_fixtures_dir() -> Path:
    return FIXTURES_DIR


@dataclass
class MockAgent:
    """Records prompt calls and returns a canned response."""
    canned_text: str = "MOCK_AGENT_RESPONSE"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(
        self,
        prompt: str,
        *,
        model: str = "haiku",
        images: list[bytes] | None = None,
    ) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model,
                           "n_images": len(images) if images else 0})
        return AgentResponse(
            text=self.canned_text,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@pytest.fixture
def mock_agent() -> MockAgent:
    return MockAgent()


@dataclass
class MockFetcher:
    responses: dict[str, str] = field(default_factory=dict)
    calls: list[str] = field(default_factory=list)

    def fetch(self, url: str) -> str:
        self.calls.append(url)
        if url in self.responses:
            return self.responses[url]
        return "<html><body>Default mock body.</body></html>"


@pytest.fixture
def mock_fetcher() -> MockFetcher:
    return MockFetcher()
```

- [ ] **Step 5: Run pytest to verify nothing breaks**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest tests/builder/ingest -v
```

Expected: existing 9 ingest tests still pass, no new tests yet.

- [ ] **Step 6: Commit**

```bash
git add tests/builder/ingest/conftest.py tests/builder/ingest/fixtures/
git commit -m "test(builder/ingest): conftest with sample fixtures and mocks"
```

---

## Task 4: PassthroughConverter

**Files:**
- Create: `src/builder/ingest/passthrough.py`
- Create: `tests/builder/ingest/test_passthrough.py`

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_passthrough.py`**

```python
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
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/ingest/passthrough.py`**

```python
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
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/passthrough.py tests/builder/ingest/test_passthrough.py
git commit -m "feat(builder/ingest): PassthroughConverter for .md files"
```

---

## Task 5: PandocConverter

**Files:**
- Create: `src/builder/ingest/pandoc_converter.py`
- Create: `tests/builder/ingest/test_pandoc_converter.py`

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_pandoc_converter.py`**

```python
import shutil
from datetime import datetime, timezone

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pandoc_converter import PandocConverter


pytestmark = pytest.mark.skipif(
    shutil.which("pandoc") is None,
    reason="pandoc not installed",
)


def test_pandoc_converts_html(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "simple.html")

    assert "Heading One" in result.content
    assert result.meta.extraction_method == ExtractionMethod.PANDOC
    assert result.meta.source_type == "html"


def test_pandoc_converts_txt(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "plain.txt")

    assert "plain text document" in result.content.lower()
    assert result.meta.extraction_method == ExtractionMethod.PANDOC
    assert result.meta.source_type == "txt"


def test_pandoc_outline_from_html_headings(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "simple.html")

    assert "Heading One" in result.meta.outline
    assert "Heading Two" in result.meta.outline


def test_pandoc_extracted_chars_matches_content(ingest_fixtures_dir):
    conv = PandocConverter()
    result = conv.convert(ingest_fixtures_dir / "plain.txt")
    assert result.meta.extracted_chars == len(result.content)


def test_pandoc_raises_when_missing(monkeypatch, ingest_fixtures_dir):
    monkeypatch.setattr("builder.ingest.pandoc_converter.shutil.which",
                        lambda _: None)
    conv = PandocConverter()
    with pytest.raises(RuntimeError, match="pandoc"):
        conv.convert(ingest_fixtures_dir / "plain.txt")
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/ingest/pandoc_converter.py`**

```python
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
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/pandoc_converter.py tests/builder/ingest/test_pandoc_converter.py
git commit -m "feat(builder/ingest): PandocConverter for txt/html/docx/rtf"
```

---

## Task 6: Tiny PDF Fixture + PDFTextExtractor

**Files:**
- Create: `tests/builder/ingest/fixtures/tiny.pdf` (binary, generated)
- Create: `src/builder/ingest/pdf_text.py`
- Create: `tests/builder/ingest/test_pdf_text.py`

- [ ] **Step 1: Generate the tiny.pdf fixture using pandoc**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
mkdir -p tests/builder/ingest/fixtures
echo -e "# Sample Heading\n\nThis is body content of a tiny test PDF.\n\n## Section\n\nMore body.\n" > /tmp/tiny.md
pandoc /tmp/tiny.md -o tests/builder/ingest/fixtures/tiny.pdf 2>/dev/null \
  || pandoc /tmp/tiny.md -t html | pandoc -f html -o tests/builder/ingest/fixtures/tiny.pdf
ls -la tests/builder/ingest/fixtures/tiny.pdf
```

If pandoc cannot generate PDF (missing latex), use a different approach — generate with a Python tool:

```bash
python -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/builder/ingest/fixtures/tiny.pdf')
c.drawString(100, 800, 'Sample Heading')
c.drawString(100, 770, 'This is body content of a tiny test PDF.')
c.drawString(100, 740, 'Section')
c.drawString(100, 710, 'More body.')
c.showPage()
c.save()
" 2>/dev/null || echo "reportlab missing — install or use a checked-in PDF"
```

If neither works, fall back: create the file `tests/builder/ingest/fixtures/tiny.pdf` by base64-decoding a checked-in minimal PDF. Use this minimal PDF (paste it as bytes):

A minimal valid PDF the agent can create with: produce a tiny PDF with `pdftotext` reading "Sample Heading\nMore body content here."

If your system can't generate one easily, create the tests with `monkeypatch` to call pdftotext on a file that contains the expected bytes — or use this approach: create a PDF programmatically with stdlib `subprocess` calling the `enscript`/`ps2pdf` chain if available.

**Pragmatic fallback:** generate by hand:
```bash
echo "Sample Heading. This is body content of a tiny test PDF. Section. More body content here that has enough text to pass the chars-per-page heuristic without triggering vision fallback for our tests." > /tmp/tiny.txt
# Use macOS' textutil or pandoc with --pdf-engine variants
pandoc /tmp/tiny.txt -o tests/builder/ingest/fixtures/tiny.pdf --pdf-engine=context 2>/dev/null \
  || pandoc /tmp/tiny.txt -o tests/builder/ingest/fixtures/tiny.pdf --pdf-engine=wkhtmltopdf 2>/dev/null \
  || pandoc /tmp/tiny.txt -o tests/builder/ingest/fixtures/tiny.pdf --pdf-engine=weasyprint 2>/dev/null \
  || pandoc /tmp/tiny.txt -o tests/builder/ingest/fixtures/tiny.pdf 2>&1 | head -3
```

Verify the file was created (size > 100 bytes) and pdftotext can read it:
```bash
pdftotext tests/builder/ingest/fixtures/tiny.pdf -
```

If you cannot generate any PDF, **report BLOCKED** with a clear description of which generators were missing.

- [ ] **Step 2: Write failing test `tests/builder/ingest/test_pdf_text.py`**

```python
import shutil

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pdf_text import (
    DEFAULT_MIN_CHARS_PER_PAGE,
    PDFTextExtractor,
    PDFTextResult,
    is_text_extraction_plausible,
)


pytestmark = pytest.mark.skipif(
    shutil.which("pdftotext") is None,
    reason="pdftotext not installed",
)


def test_pdftext_extracts_content(ingest_fixtures_dir):
    ext = PDFTextExtractor()
    result = ext.extract(ingest_fixtures_dir / "tiny.pdf")

    assert isinstance(result, PDFTextResult)
    assert result.page_count >= 1
    assert len(result.text) > 0
    assert "body content" in result.text.lower() or "sample" in result.text.lower()


def test_plausibility_check_passes_for_normal_text():
    """A typical text page (200+ chars) is plausible."""
    sample = "x" * 250
    assert is_text_extraction_plausible(sample, page_count=1) is True


def test_plausibility_check_fails_for_empty():
    assert is_text_extraction_plausible("", page_count=10) is False


def test_plausibility_check_fails_below_min_chars_per_page():
    sample = "tiny"  # 4 chars
    # 4/10 = 0.4 chars/page, way below default 200
    assert is_text_extraction_plausible(sample, page_count=10) is False


def test_plausibility_threshold_configurable():
    sample = "x" * 100
    # At default 200 chars/page on 1 page → fails
    assert is_text_extraction_plausible(sample, page_count=1) is False
    # At threshold 50 → passes
    assert is_text_extraction_plausible(sample, page_count=1,
                                          min_chars_per_page=50) is True


def test_default_threshold_constant():
    assert DEFAULT_MIN_CHARS_PER_PAGE == 200


def test_extractor_produces_convert_result(ingest_fixtures_dir):
    """Higher-level interface: convert() returns a ConvertResult with TEXT method
    when extraction is plausible."""
    ext = PDFTextExtractor()
    result = ext.convert(ingest_fixtures_dir / "tiny.pdf")
    assert result.meta.extraction_method == ExtractionMethod.TEXT
    assert result.meta.source_type == "pdf"
    assert result.meta.extracted_chars == len(result.content)


def test_extractor_raises_when_pdftotext_missing(monkeypatch, ingest_fixtures_dir):
    monkeypatch.setattr("builder.ingest.pdf_text.shutil.which",
                        lambda _: None)
    ext = PDFTextExtractor()
    with pytest.raises(RuntimeError, match="pdftotext"):
        ext.extract(ingest_fixtures_dir / "tiny.pdf")
```

- [ ] **Step 3: Run → fail**

- [ ] **Step 4: Implement `src/builder/ingest/pdf_text.py`**

```python
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


def _count_pdf_pages(path: Path) -> int:
    """Count pages by parsing pdftotext output's form-feed count + 1."""
    proc = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        return 0
    return proc.stdout.count("\f") + 1


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
```

- [ ] **Step 5: Run → 8 pass**

- [ ] **Step 6: Commit**

```bash
git add tests/builder/ingest/fixtures/tiny.pdf src/builder/ingest/pdf_text.py tests/builder/ingest/test_pdf_text.py
git commit -m "feat(builder/ingest): PDFTextExtractor + plausibility heuristic"
```

---

## Task 7: VisionPDFConverter

**Files:**
- Create: `src/builder/ingest/pdf_vision.py`
- Create: `tests/builder/ingest/test_pdf_vision.py`

The Vision converter renders each PDF page to an image (via `pdftoppm`), passes the image bytes to the AgentCaller, and concatenates the responses into the body content.

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_pdf_vision.py`**

```python
import shutil

import pytest

from builder.ingest.meta import ExtractionMethod
from builder.ingest.pdf_vision import VisionPDFConverter


pytestmark = pytest.mark.skipif(
    shutil.which("pdftoppm") is None,
    reason="pdftoppm not installed",
)


def test_vision_converter_calls_agent_per_page(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    result = conv.convert(ingest_fixtures_dir / "tiny.pdf")

    # At least one agent call (one per page).
    assert len(mock_agent.calls) >= 1
    # Each call carries images.
    for call in mock_agent.calls:
        assert call["n_images"] == 1


def test_vision_converter_uses_sonnet_by_default(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    conv.convert(ingest_fixtures_dir / "tiny.pdf")
    for call in mock_agent.calls:
        assert call["model"] == "sonnet"


def test_vision_converter_meta(ingest_fixtures_dir, mock_agent):
    conv = VisionPDFConverter(agent=mock_agent)
    result = conv.convert(ingest_fixtures_dir / "tiny.pdf")

    assert result.meta.source_type == "pdf"
    assert result.meta.extraction_method == ExtractionMethod.VISION_FALLBACK
    assert result.meta.page_count >= 1
    # Body assembled from agent responses.
    assert "MOCK_AGENT_RESPONSE" in result.content
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/ingest/pdf_vision.py`**

```python
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
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/pdf_vision.py tests/builder/ingest/test_pdf_vision.py
git commit -m "feat(builder/ingest): VisionPDFConverter via AgentCaller"
```

---

## Task 8: URL Fetcher

**Files:**
- Create: `src/builder/ingest/url_fetch.py`
- Create: `tests/builder/ingest/test_url_fetch.py`

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_url_fetch.py`**

```python
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
```

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/ingest/url_fetch.py`**

```python
"""URL fetcher — converts an HTTP(S) URL's HTML body to markdown."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser

from builder.ingest.meta import DocumentMeta, ExtractionMethod
from builder.ingest.protocols import ConvertResult, HTTPFetcher


HEADING_PATTERN = re.compile(r"^#{1,6}\s+(.+?)\s*$", re.MULTILINE)


class _HTMLToMarkdown(HTMLParser):
    """Lightweight HTML → markdown converter for the URL ingest path.

    Handles h1-h6, p, br, strong, em, code. Drops scripts/styles/title/head.
    Adequate for typical documentation pages; not a full converter.
    """

    HEADINGS = {"h1": "# ", "h2": "## ", "h3": "### ",
                "h4": "#### ", "h5": "##### ", "h6": "###### "}

    def __init__(self) -> None:
        super().__init__()
        self._out: list[str] = []
        self._skip = 0
        self._heading_prefix: str | None = None

    def handle_starttag(self, tag: str, attrs):
        if tag in {"script", "style", "head"}:
            self._skip += 1
            return
        if tag in self.HEADINGS:
            self._out.append("\n\n")
            self._heading_prefix = self.HEADINGS[tag]
            self._out.append(self._heading_prefix)
        elif tag in {"p", "div", "br", "li"}:
            self._out.append("\n\n")
        elif tag == "strong" or tag == "b":
            self._out.append("**")
        elif tag == "em" or tag == "i":
            self._out.append("*")
        elif tag == "code":
            self._out.append("`")

    def handle_endtag(self, tag: str):
        if tag in {"script", "style", "head"}:
            self._skip = max(0, self._skip - 1)
            return
        if tag in self.HEADINGS:
            self._heading_prefix = None
            self._out.append("\n\n")
        elif tag == "strong" or tag == "b":
            self._out.append("**")
        elif tag == "em" or tag == "i":
            self._out.append("*")
        elif tag == "code":
            self._out.append("`")

    def handle_data(self, data: str):
        if self._skip:
            return
        self._out.append(data)

    def result(self) -> str:
        text = "".join(self._out)
        # Collapse 3+ newlines to 2.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip() + "\n"


class URLFetchConverter:
    """Fetch a URL and convert the HTML body to markdown."""

    def __init__(self, fetcher: HTTPFetcher) -> None:
        self._fetcher = fetcher

    def convert_url(self, url: str) -> ConvertResult:
        html = self._fetcher.fetch(url)
        parser = _HTMLToMarkdown()
        parser.feed(html)
        content = parser.result()
        outline = [m.group(1) for m in HEADING_PATTERN.finditer(content)]

        meta = DocumentMeta(
            source_path=url,
            source_type="url",
            extraction_method=ExtractionMethod.URL_FETCH,
            page_count=1,
            extracted_chars=len(content),
            extracted_images_count=0,
            outline=outline,
            language_detected="und",
            ingested=datetime.now(timezone.utc).date(),
        )
        return ConvertResult(content=content, meta=meta)
```

- [ ] **Step 4: Run → 3 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/url_fetch.py tests/builder/ingest/test_url_fetch.py
git commit -m "feat(builder/ingest): URLFetchConverter with HTML→markdown"
```

---

## Task 9: Ingest Orchestrator

**Files:**
- Create: `src/builder/ingest/orchestrator.py`
- Create: `tests/builder/ingest/test_orchestrator.py`

The orchestrator picks a converter by extension, runs the PDF plausibility check, falls back to vision, integrates with `Pipeline.record_item` and `record_cost`.

- [ ] **Step 1: Write failing test `tests/builder/ingest/test_orchestrator.py`**

```python
from pathlib import Path

from builder.ingest.orchestrator import IngestOrchestrator
from builder.phases import Phase
from builder.pipeline import Pipeline


def test_orchestrator_handles_md_file(ingest_fixtures_dir, mock_agent, mock_fetcher,
                                       run_dir):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(
        ingest_fixtures_dir, pipeline=pipeline, only_files=["plain.md"],
    )

    assert len(results) == 1
    assert "plain.md" in results
    item = pipeline.state.phases["ingest"].items["plain.md"]
    assert item.status == "done"
    assert item.metadata["extraction_method"] == "passthrough"


def test_orchestrator_handles_url(mock_agent, mock_fetcher, ingest_fixtures_dir,
                                    run_dir):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir,
        url_list=["https://example.com/spec"], run_dir=run_dir,
    )
    mock_fetcher.responses["https://example.com/spec"] = "<h1>S</h1><p>body</p>"
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)

    results = orch.ingest_urls(["https://example.com/spec"], pipeline=pipeline)

    assert "https://example.com/spec" in results
    items = pipeline.state.phases["ingest"].items
    assert items["https://example.com/spec"].status == "done"
    assert items["https://example.com/spec"].metadata["extraction_method"] == "url_fetch"


def test_orchestrator_failed_url_marks_item_failed(mock_agent, ingest_fixtures_dir, run_dir):
    """A fetcher that raises causes the item to be marked failed."""
    class FailingFetcher:
        def fetch(self, url: str) -> str:
            raise RuntimeError("network down")

    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=FailingFetcher())
    results = orch.ingest_urls(["https://x"], pipeline=pipeline)

    assert "https://x" not in results
    assert pipeline.state.phases["ingest"].items["https://x"].status == "failed"
    assert "network down" in (pipeline.state.phases["ingest"].items["https://x"].error or "")


def test_orchestrator_dispatches_pdf_to_text_when_plausible(
    ingest_fixtures_dir, mock_agent, mock_fetcher, run_dir,
):
    pipeline = Pipeline.create(
        run_id="x", input_dir=ingest_fixtures_dir, url_list=[], run_dir=run_dir,
    )
    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(
        ingest_fixtures_dir, pipeline=pipeline, only_files=["tiny.pdf"],
    )
    assert "tiny.pdf" in results
    item = pipeline.state.phases["ingest"].items["tiny.pdf"]
    # tiny.pdf has enough text → text extraction succeeds, no vision calls.
    assert item.metadata["extraction_method"] == "text"
    assert mock_agent.calls == []  # vision not invoked


def test_orchestrator_unknown_extension_marks_failed(
    tmp_path: Path, mock_agent, mock_fetcher, run_dir,
):
    pipeline = Pipeline.create(
        run_id="x", input_dir=tmp_path, url_list=[], run_dir=run_dir,
    )
    bad = tmp_path / "weird.xyz"
    bad.write_text("hi")

    orch = IngestOrchestrator(agent=mock_agent, fetcher=mock_fetcher)
    results = orch.ingest_directory(tmp_path, pipeline=pipeline,
                                     only_files=["weird.xyz"])
    assert "weird.xyz" not in results
    assert pipeline.state.phases["ingest"].items["weird.xyz"].status == "failed"
```

Note: `run_dir` fixture comes from `tests/builder/conftest.py` (parent conftest is auto-loaded by pytest).

- [ ] **Step 2: Run → fail**

- [ ] **Step 3: Implement `src/builder/ingest/orchestrator.py`**

```python
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
```

- [ ] **Step 4: Run → 5 pass**

- [ ] **Step 5: Commit**

```bash
git add src/builder/ingest/orchestrator.py tests/builder/ingest/test_orchestrator.py
git commit -m "feat(builder/ingest): orchestrator dispatches converters + records to Pipeline"
```

---

## Task 10: Public API + Integration

**Files:**
- Modify: `src/builder/ingest/__init__.py`
- Create: `tests/builder/ingest/test_public_api.py`

- [ ] **Step 1: Update `src/builder/ingest/__init__.py`**

```python
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
```

- [ ] **Step 2: Write `tests/builder/ingest/test_public_api.py`**

```python
def test_ingest_public_api():
    from builder.ingest import (
        DocumentMeta, ExtractionMethod,
        AgentCaller, AgentResponse,
        Converter, ConvertResult,
        HTTPFetcher,
        PassthroughConverter, PandocConverter,
        PDFTextExtractor, PDFTextResult,
        DEFAULT_MIN_CHARS_PER_PAGE, is_text_extraction_plausible,
        VisionPDFConverter,
        URLFetchConverter,
        IngestOrchestrator,
    )
    assert DEFAULT_MIN_CHARS_PER_PAGE == 200
    assert callable(is_text_extraction_plausible)
```

- [ ] **Step 3: Run all tests**

```bash
cd /Users/szymanski/Projects/matter_expert_skill_creator_skill
source .venv/bin/activate
pytest
```

Expected: all tests pass across all packages.

- [ ] **Step 4: Commit**

```bash
git add src/builder/ingest/__init__.py tests/builder/ingest/test_public_api.py
git commit -m "feat(builder/ingest): public API exports"
```

---

## Done — what you have after this plan

After completing all 10 tasks, the Ingest phase provides:

1. **Document metadata** — DocumentMeta + 6 ExtractionMethod values
2. **Pluggable protocols** — Converter / AgentCaller / HTTPFetcher (mock-friendly)
3. **5 converters** — Passthrough (md), Pandoc (txt/html/docx/rtf), PDFText, VisionPDF, URLFetch
4. **Plausibility heuristic** — is_text_extraction_plausible (default 200 chars/page)
5. **Orchestrator** — dispatches by extension + URL list, integrates with Pipeline
6. **Real CLI integration** — pandoc, pdftotext, pdftoppm verified available
7. **Mocked LLM/HTTP** — tests don't make real API or network calls
