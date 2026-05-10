"""Production AgentCaller using the Anthropic SDK (imported lazily)."""
from __future__ import annotations

import base64
import os

from builder.ingest.protocols import AgentResponse


# Map our model identifier → Anthropic API model ID. These map to current
# stable model versions; update when newer models are released.
MODEL_ID_MAP = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-7",
}


DEFAULT_MAX_TOKENS = 4096


class AnthropicAgent:
    """AgentCaller that delegates to the Anthropic Messages API."""

    def __init__(
        self,
        client=None,
        api_key: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        if client is None:
            # Lazy import so test envs without the SDK still work.
            import anthropic
            client = anthropic.Anthropic(
                api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            )
        self._client = client
        self._max_tokens = max_tokens

    def call(
        self,
        prompt: str,
        *,
        model: str = "haiku",
        images: list[bytes] | None = None,
    ) -> AgentResponse:
        sdk_model = MODEL_ID_MAP.get(model, model)
        content_blocks: list[dict] = []
        for img in images or []:
            content_blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": base64.b64encode(img).decode("ascii"),
                },
            })
        content_blocks.append({"type": "text", "text": prompt})

        response = self._client.messages.create(
            model=sdk_model,
            max_tokens=self._max_tokens,
            messages=[{"role": "user", "content": content_blocks}],
        )
        text = "".join(
            block.text for block in response.content
            if getattr(block, "text", None)
        )
        return AgentResponse(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cached_input_tokens=getattr(
                response.usage, "cache_read_input_tokens", 0,
            ) or 0,
        )
