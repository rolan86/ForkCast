"""Tests for Anthropic prompt caching support in ClaudeClient."""

import copy
from unittest.mock import MagicMock, patch

from forkcast.llm.client import ClaudeClient


def _mock_anthropic_client():
    """Create a mock Anthropic client with a valid response."""
    mock = MagicMock()
    mock.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="test response")],
        usage=MagicMock(input_tokens=10, output_tokens=20),
        model="claude-sonnet-4-6",
        stop_reason="end_turn",
    )
    return mock


class TestPromptCachingToolUse:
    def test_tool_use_accepts_use_cache_param(self):
        client = ClaudeClient(api_key="test-key")
        client._client = _mock_anthropic_client()
        client.tool_use(
            messages=[{"role": "user", "content": "test"}],
            tools=[{"name": "test", "description": "test", "input_schema": {"type": "object", "properties": {}}}],
            system="You are helpful",
            use_cache=True,
        )

    def test_cache_enabled_converts_system_to_content_blocks(self):
        client = ClaudeClient(api_key="test-key")
        client._client = _mock_anthropic_client()
        client.tool_use(
            messages=[{"role": "user", "content": "test"}],
            tools=[{"name": "test", "description": "test", "input_schema": {"type": "object", "properties": {}}}],
            system="You are a test agent",
            use_cache=True,
        )
        call_kwargs = client._client.messages.create.call_args[1]
        system = call_kwargs["system"]
        assert isinstance(system, list), "system should be a list of content blocks"
        assert system[0]["type"] == "text"
        assert system[0]["text"] == "You are a test agent"
        assert system[0]["cache_control"] == {"type": "ephemeral"}

    def test_cache_enabled_adds_cache_control_to_last_tool(self):
        client = ClaudeClient(api_key="test-key")
        client._client = _mock_anthropic_client()
        tools = [
            {"name": "tool_a", "description": "A", "input_schema": {"type": "object", "properties": {}}},
            {"name": "tool_b", "description": "B", "input_schema": {"type": "object", "properties": {}}},
        ]
        client.tool_use(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
            system="system prompt",
            use_cache=True,
        )
        call_kwargs = client._client.messages.create.call_args[1]
        sent_tools = call_kwargs["tools"]
        assert sent_tools[-1]["cache_control"] == {"type": "ephemeral"}
        assert "cache_control" not in sent_tools[0]

    def test_cache_disabled_leaves_system_as_string(self):
        client = ClaudeClient(api_key="test-key")
        client._client = _mock_anthropic_client()
        client.tool_use(
            messages=[{"role": "user", "content": "test"}],
            tools=[{"name": "test", "description": "test", "input_schema": {"type": "object", "properties": {}}}],
            system="plain system",
        )
        call_kwargs = client._client.messages.create.call_args[1]
        assert call_kwargs["system"] == "plain system"

    def test_cache_does_not_mutate_original_tools(self):
        client = ClaudeClient(api_key="test-key")
        client._client = _mock_anthropic_client()
        tools = [
            {"name": "tool_a", "description": "A", "input_schema": {"type": "object", "properties": {}}},
        ]
        original_tools = copy.deepcopy(tools)
        client.tool_use(
            messages=[{"role": "user", "content": "test"}],
            tools=tools,
            system="system",
            use_cache=True,
        )
        assert tools == original_tools
