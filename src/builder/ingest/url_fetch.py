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
