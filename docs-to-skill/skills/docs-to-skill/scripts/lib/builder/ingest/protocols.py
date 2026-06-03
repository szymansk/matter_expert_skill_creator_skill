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
class AgentResponse:
    """LLM response for an agent call (used by vision fallback, etc.)."""
    text: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int = 0


@dataclass(frozen=True)
class ConvertResult:
    """Output of a Converter — markdown body + extraction metadata.

    `token_usage` is populated by converters that make LLM calls (e.g.
    VisionPDFConverter) so the orchestrator can record costs to the Pipeline.
    Local-only converters leave it as None.
    """
    content: str
    meta: DocumentMeta
    token_usage: AgentResponse | None = None


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
