from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from builder.ingest.protocols import AgentResponse


@dataclass
class CannedAgent:
    canned_text: str = "MOCK_TRIGGER_DESCRIPTION"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(self, prompt, *, model="haiku", images=None) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model})
        return AgentResponse(
            text=self.canned_text,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()
