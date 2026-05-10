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
