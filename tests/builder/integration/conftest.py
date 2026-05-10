"""Fixtures for integration tests.

Reuses CannedAgent and a small input directory fixture.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "{}"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(self, prompt, *, model="haiku", images=None) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model})
        for needle, text in self.recipes.items():
            if needle in prompt:
                return AgentResponse(
                    text=text,
                    input_tokens=self.canned_input_tokens,
                    output_tokens=self.canned_output_tokens,
                )
        return AgentResponse(
            text=self.default,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@dataclass
class MockFetcher:
    responses: dict[str, str] = field(default_factory=dict)

    def fetch(self, url: str) -> str:
        return self.responses.get(url, "<html><body>default</body></html>")


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()


@pytest.fixture
def mock_fetcher() -> MockFetcher:
    return MockFetcher()


@pytest.fixture
def sample_input_dir(tmp_path: Path) -> Path:
    """A directory with one markdown document for an end-to-end build."""
    d = tmp_path / "inputs"
    d.mkdir()
    (d / "handbook.md").write_text(
        "# Handbook\n\n"
        "## Authentication\n\n"
        "Authentication verifies who you are.\n\n"
        "## Authorization\n\n"
        "Authorization decides what you can do.\n",
        encoding="utf-8",
    )
    return d


def _outline_json() -> str:
    return json.dumps({"entries": [
        {"concept_name": "authentication", "title": "Authentication",
         "source_sections": [], "estimated_tokens": 600},
        {"concept_name": "authorization", "title": "Authorization",
         "source_sections": [], "estimated_tokens": 600},
    ]})


@pytest.fixture
def full_pipeline_agent(canned_agent: CannedAgent) -> CannedAgent:
    """Pre-loaded CannedAgent with recipes for a full end-to-end build."""
    canned_agent.recipes["Identify the atomic concepts"] = _outline_json()
    canned_agent.recipes["Output the concept's markdown body only."] = "# Concept\n\nBody.\n"
    canned_agent.recipes["Source outline"] = json.dumps({"missed_topics": []})
    canned_agent.recipes["Inventory"] = json.dumps({"clusters": []})
    canned_agent.recipes["Return typed-link JSON only."] = json.dumps({
        "related": [], "prerequisites": [], "examples": [],
        "contrasts": [], "refines": [],
    })
    # QA validators: all pass
    canned_agent.default = json.dumps({
        "verdict": "pass", "reasons": [],
        "missed_topics": [], "unsupported_claims": [], "issues": [],
    })
    return canned_agent
