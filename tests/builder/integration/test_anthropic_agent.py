from unittest.mock import MagicMock, patch

import pytest

from builder.integration.anthropic_agent import (
    AnthropicAgent,
    MODEL_ID_MAP,
)


def test_model_id_map_covers_all_models():
    assert "haiku" in MODEL_ID_MAP
    assert "sonnet" in MODEL_ID_MAP
    assert "opus" in MODEL_ID_MAP


def test_call_invokes_sdk_with_correct_model():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="response text")]
    mock_response.usage.input_tokens = 100
    mock_response.usage.output_tokens = 50
    mock_response.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("test prompt", model="haiku")

    assert response.text == "response text"
    assert response.input_tokens == 100
    assert response.output_tokens == 50
    # Called with the mapped Haiku model ID
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["model"] == MODEL_ID_MAP["haiku"]


def test_call_includes_images_when_provided():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 10
    mock_response.usage.cache_read_input_tokens = 0
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("describe this", model="sonnet",
                            images=[b"\x89PNG\r\n\x1a\n"])

    assert response.text == "ok"
    # Image content block included
    messages = mock_client.messages.create.call_args.kwargs["messages"]
    content = messages[0]["content"]
    assert any(
        block.get("type") == "image" for block in content if isinstance(block, dict)
    )


def test_call_propagates_cached_input_tokens():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="ok")]
    mock_response.usage.input_tokens = 0
    mock_response.usage.output_tokens = 100
    mock_response.usage.cache_read_input_tokens = 500
    mock_client.messages.create.return_value = mock_response

    agent = AnthropicAgent(client=mock_client, api_key="sk-x")
    response = agent.call("prompt", model="haiku")

    assert response.cached_input_tokens == 500
