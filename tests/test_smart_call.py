"""Tests for ClaudeClient.smart_call() dispatch."""
from unittest.mock import MagicMock
from forkcast.llm.client import ClaudeClient, _model_supports_thinking


class TestModelSupportsThinking:
    def test_haiku_does_not_support_thinking(self):
        assert _model_supports_thinking("claude-haiku-4-5") is False

    def test_sonnet_supports_thinking(self):
        assert _model_supports_thinking("claude-sonnet-4-6") is True

    def test_unknown_model_defaults_to_false(self):
        assert _model_supports_thinking("unknown-model-9000") is False


class TestSmartCall:
    def test_routes_to_think_for_sonnet(self):
        client = ClaudeClient.__new__(ClaudeClient)
        client._client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think = MagicMock(return_value="think_result")
        client.complete = MagicMock(return_value="complete_result")

        result = client.smart_call(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "test"}],
            system="sys",
        )
        client.think.assert_called_once()
        client.complete.assert_not_called()
        assert result == "think_result"

    def test_routes_to_complete_for_haiku(self):
        client = ClaudeClient.__new__(ClaudeClient)
        client._client = MagicMock()
        client.default_model = "claude-haiku-4-5"
        client.think = MagicMock(return_value="think_result")
        client.complete = MagicMock(return_value="complete_result")

        result = client.smart_call(
            model="claude-haiku-4-5",
            messages=[{"role": "user", "content": "test"}],
            system="sys",
        )
        client.complete.assert_called_once()
        client.think.assert_not_called()
        assert result == "complete_result"

    def test_passes_thinking_budget(self):
        client = ClaudeClient.__new__(ClaudeClient)
        client._client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think = MagicMock(return_value="think_result")

        client.smart_call(
            model="claude-sonnet-4-6",
            messages=[{"role": "user", "content": "test"}],
            system="sys",
            thinking_budget=5000,
        )
        _, kwargs = client.think.call_args
        assert kwargs.get("thinking_budget") == 5000
