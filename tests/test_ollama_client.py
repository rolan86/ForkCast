"""Unit tests for OllamaClient (all API calls mocked)."""

import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("openai.OpenAI") as mock_cls:
        mock_instance = MagicMock()
        mock_cls.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def client(mock_openai):
    from forkcast.llm.ollama_client import OllamaClient
    return OllamaClient(base_url="http://localhost:11434/v1", default_model="llama3.1")


def _make_completion(text="Hello", tool_calls=None):
    """Helper to create a mock completion response."""
    choice = MagicMock()
    choice.message.content = text
    choice.message.tool_calls = tool_calls
    choice.finish_reason = "stop"

    response = MagicMock()
    response.choices = [choice]
    response.usage.prompt_tokens = 10
    response.usage.completion_tokens = 20
    response.model = "llama3.1"
    return response


class TestComplete:
    def test_complete_basic(self, client, mock_openai):
        mock_openai.chat.completions.create.return_value = _make_completion("Hi there")
        result = client.complete(messages=[{"role": "user", "content": "Hello"}])
        assert result.text == "Hi there"
        assert result.input_tokens == 10
        assert result.output_tokens == 20

    def test_complete_with_system(self, client, mock_openai):
        mock_openai.chat.completions.create.return_value = _make_completion("OK")
        client.complete(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are helpful",
        )
        call_args = mock_openai.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert messages[0] == {"role": "system", "content": "You are helpful"}
        assert messages[1] == {"role": "user", "content": "Hi"}


class TestToolUse:
    def test_tool_use_translates_schema(self, client, mock_openai):
        """Anthropic tool schema is translated to OpenAI function-calling format."""
        tool_call = MagicMock()
        tool_call.id = "call_123"
        tool_call.function.name = "web_search"
        tool_call.function.arguments = json.dumps({"query": "test"})

        mock_openai.chat.completions.create.return_value = _make_completion(
            text="", tool_calls=[tool_call]
        )

        anthropic_tools = [
            {"name": "web_search", "description": "Search the web", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}}
        ]

        result = client.tool_use(
            messages=[{"role": "user", "content": "search for test"}],
            tools=anthropic_tools,
        )

        # Verify schema was translated to OpenAI format
        call_args = mock_openai.chat.completions.create.call_args
        openai_tools = call_args[1]["tools"]
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "web_search"
        assert openai_tools[0]["function"]["parameters"] == anthropic_tools[0]["input_schema"]

        # Verify response was translated back
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0]["id"] == "call_123"
        assert result.tool_calls[0]["name"] == "web_search"
        assert result.tool_calls[0]["input"] == {"query": "test"}

    def test_tool_use_fallback_on_bad_request(self, client, mock_openai):
        """Falls back to structured prompting when model doesn't support tools."""
        import openai
        mock_openai.chat.completions.create.side_effect = [
            openai.BadRequestError(
                message="does not support tools",
                response=MagicMock(status_code=400),
                body=None,
            ),
            _make_completion(text=json.dumps({"name": "web_search", "input": {"query": "test"}})),
        ]

        result = client.tool_use(
            messages=[{"role": "user", "content": "search"}],
            tools=[{"name": "web_search", "description": "Search", "input_schema": {"type": "object"}}],
        )

        # Second call should NOT have tools param (structured prompting fallback)
        second_call = mock_openai.chat.completions.create.call_args_list[1]
        assert "tools" not in second_call[1]
        assert result.tool_calls[0]["name"] == "web_search"


class TestThinkAndSmartCall:
    def test_think_delegates_to_complete(self, client, mock_openai):
        """think() delegates to complete() — no extended thinking for Ollama."""
        mock_openai.chat.completions.create.return_value = _make_completion("thought result")
        result = client.think(messages=[{"role": "user", "content": "think hard"}])
        assert result.text == "thought result"

    def test_smart_call_routes_to_complete(self, client, mock_openai):
        """smart_call() always routes to complete()."""
        mock_openai.chat.completions.create.return_value = _make_completion("smart result")
        result = client.smart_call(
            model="llama3.1",
            messages=[{"role": "user", "content": "be smart"}],
        )
        assert result.text == "smart result"


class TestStream:
    def test_stream_yields_events(self, client, mock_openai):
        """stream() translates OpenAI streaming events to StreamEvent."""
        # Create mock streaming chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Hello"
        chunk1.choices[0].delta.tool_calls = None
        chunk1.choices[0].finish_reason = None

        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " world"
        chunk2.choices[0].delta.tool_calls = None
        chunk2.choices[0].finish_reason = "stop"

        mock_openai.chat.completions.create.return_value = iter([chunk1, chunk2])

        events = list(client.stream(messages=[{"role": "user", "content": "Hi"}]))
        text_events = [e for e in events if e.type == "text_delta"]
        done_events = [e for e in events if e.type == "done"]
        assert len(text_events) == 2
        assert text_events[0].data == "Hello"
        assert text_events[1].data == " world"
        assert len(done_events) == 1


class TestConnectionError:
    def test_connection_error_gives_helpful_message(self, mock_openai):
        """Raises ConnectionError with helpful message when Ollama unreachable."""
        import openai
        from forkcast.llm.ollama_client import OllamaClient

        client = OllamaClient(base_url="http://localhost:11434/v1", default_model="llama3.1")
        mock_openai.chat.completions.create.side_effect = openai.APIConnectionError(
            request=MagicMock()
        )

        with pytest.raises(ConnectionError, match="Cannot connect to Ollama"):
            client.complete(messages=[{"role": "user", "content": "hi"}])


class TestRetry:
    def test_retry_on_api_error(self, client, mock_openai):
        """Retries on APIError with exponential backoff."""
        import openai
        mock_openai.chat.completions.create.side_effect = [
            openai.APIError(
                message="server error",
                request=MagicMock(),
                body=None,
            ),
            _make_completion("recovered"),
        ]

        with patch("time.sleep"):  # Don't actually sleep
            result = client.complete(messages=[{"role": "user", "content": "hi"}])
        assert result.text == "recovered"
