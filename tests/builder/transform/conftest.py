"""Fixtures for transform tests.

`canned_agent` returns scripted responses based on prompt content,
simulating an LLM that produces consistent JSON outlines and markdown
extractions for our test inputs.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    """An AgentCaller that returns scripted text per prompt-substring match.

    `recipes` maps a substring to a canned text. The first matching recipe
    wins; if nothing matches, returns `default`.
    """
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "MOCK_DEFAULT_RESPONSE"
    canned_input_tokens: int = 200
    canned_output_tokens: int = 100
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


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()


@pytest.fixture
def outline_json_response() -> str:
    """A canned analyzer JSON response covering two concepts."""
    return json.dumps({
        "entries": [
            {"concept_name": "oauth2-flow", "title": "OAuth2 Flow",
             "source_sections": ["3.1", "3.2"], "estimated_tokens": 1200},
            {"concept_name": "jwt-tokens", "title": "JWT Tokens",
             "source_sections": ["3.3"], "estimated_tokens": 800},
        ]
    })
