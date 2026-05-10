"""Fixtures for link tests. Reuses CannedAgent pattern from transform."""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "MOCK_DEFAULT"
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


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()
