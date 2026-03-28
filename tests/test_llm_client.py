from unittest.mock import MagicMock, patch


def test_complete_returns_text(mock_anthropic):
    """complete() should return the text content from Claude's response."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.complete(messages=[{"role": "user", "content": "Hello"}])
    assert result.text == "mock response"
    assert result.input_tokens == 10
    assert result.output_tokens == 20


def test_complete_tracks_usage(mock_anthropic):
    """complete() should populate usage fields."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.complete(messages=[{"role": "user", "content": "test"}])
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.model is not None


def test_tool_use_extracts_tool_calls(mock_anthropic):
    """tool_use() should extract tool call blocks from the response."""
    from forkcast.llm.client import ClaudeClient

    # Set up mock to return a tool_use block
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "call_123"
    tool_block.name = "extract_entities"
    tool_block.input = {"entities": [{"name": "Alice", "type": "Person"}]}

    mock_anthropic.messages.create.return_value = MagicMock(
        content=[tool_block],
        usage=MagicMock(input_tokens=50, output_tokens=100),
        model="claude-sonnet-4-6",
        stop_reason="tool_use",
    )

    client = ClaudeClient(api_key="test-key")
    client._client = mock_anthropic

    result = client.tool_use(
        messages=[{"role": "user", "content": "Extract entities"}],
        tools=[{"name": "extract_entities", "description": "test", "input_schema": {}}],
    )

    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["name"] == "extract_entities"
    assert result.tool_calls[0]["input"]["entities"][0]["name"] == "Alice"


def test_client_default_model():
    """ClaudeClient should use a sensible default model."""
    from forkcast.llm.client import ClaudeClient

    client = ClaudeClient(api_key="test-key")
    assert "claude" in client.default_model


def test_claude_client_satisfies_llm_protocol():
    """ClaudeClient structurally satisfies LLMClient Protocol."""
    from forkcast.llm.client import LLMClient, ClaudeClient
    # Protocol structural check — verify all required methods exist
    required_methods = ["complete", "tool_use", "think", "smart_call", "stream"]
    for method in required_methods:
        assert hasattr(ClaudeClient, method), f"ClaudeClient missing {method}"
    assert hasattr(ClaudeClient, "default_model")
