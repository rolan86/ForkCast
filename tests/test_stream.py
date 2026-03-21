"""Tests for ClaudeClient.stream() method."""

from unittest.mock import MagicMock, patch

from forkcast.llm.client import ClaudeClient
from forkcast.report.models import StreamEvent


class TestStream:
    def _make_client(self):
        with patch("forkcast.llm.client.anthropic.Anthropic"):
            client = ClaudeClient(api_key="test-key")
        return client

    def test_stream_yields_text_deltas(self):
        client = self._make_client()

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        text_event1 = MagicMock()
        text_event1.type = "content_block_delta"
        text_event1.delta = MagicMock()
        text_event1.delta.type = "text_delta"
        text_event1.delta.text = "Hello"

        text_event2 = MagicMock()
        text_event2.type = "content_block_delta"
        text_event2.delta = MagicMock()
        text_event2.delta.type = "text_delta"
        text_event2.delta.text = " World"

        mock_stream.__iter__ = MagicMock(return_value=iter([text_event1, text_event2]))

        final_msg = MagicMock()
        final_msg.usage.input_tokens = 10
        final_msg.usage.output_tokens = 5
        final_msg.stop_reason = "end_turn"
        mock_stream.get_final_message.return_value = final_msg

        client._client.messages.stream = MagicMock(return_value=mock_stream)

        events = list(client.stream(
            messages=[{"role": "user", "content": "Hi"}],
        ))

        text_events = [e for e in events if e.type == "text_delta"]
        done_events = [e for e in events if e.type == "done"]

        assert len(text_events) == 2
        assert text_events[0].data == "Hello"
        assert text_events[1].data == " World"
        assert len(done_events) == 1
        assert done_events[0].data["input_tokens"] == 10
        assert done_events[0].data["stop_reason"] == "end_turn"

    def test_stream_yields_tool_use(self):
        client = self._make_client()

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)

        tool_start = MagicMock()
        tool_start.type = "content_block_start"
        tool_start.content_block = MagicMock()
        tool_start.content_block.type = "tool_use"
        tool_start.content_block.id = "tool_1"
        tool_start.content_block.name = "graph_search"

        tool_delta = MagicMock()
        tool_delta.type = "content_block_delta"
        tool_delta.delta = MagicMock()
        tool_delta.delta.type = "input_json_delta"
        tool_delta.delta.partial_json = '{"query": "AI"}'

        mock_stream.__iter__ = MagicMock(return_value=iter([tool_start, tool_delta]))

        final_msg = MagicMock()
        final_msg.usage.input_tokens = 20
        final_msg.usage.output_tokens = 15
        final_msg.stop_reason = "tool_use"
        final_msg.content = [
            MagicMock(type="tool_use", id="tool_1", name="graph_search", input={"query": "AI"}),
        ]
        mock_stream.get_final_message.return_value = final_msg

        client._client.messages.stream = MagicMock(return_value=mock_stream)

        events = list(client.stream(
            messages=[{"role": "user", "content": "Search"}],
            tools=[{"name": "graph_search", "description": "Search", "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}}}],
        ))

        tool_events = [e for e in events if e.type == "tool_use"]
        done_events = [e for e in events if e.type == "done"]

        assert len(tool_events) == 1
        assert tool_events[0].data["name"] == "graph_search"
        assert tool_events[0].data["input"] == {"query": "AI"}
        assert done_events[0].data["stop_reason"] == "tool_use"

    def test_stream_with_system_prompt(self):
        client = self._make_client()

        mock_stream = MagicMock()
        mock_stream.__enter__ = MagicMock(return_value=mock_stream)
        mock_stream.__exit__ = MagicMock(return_value=False)
        mock_stream.__iter__ = MagicMock(return_value=iter([]))
        final_msg = MagicMock()
        final_msg.usage.input_tokens = 5
        final_msg.usage.output_tokens = 3
        final_msg.stop_reason = "end_turn"
        final_msg.content = []
        mock_stream.get_final_message.return_value = final_msg

        client._client.messages.stream = MagicMock(return_value=mock_stream)

        list(client.stream(
            messages=[{"role": "user", "content": "Hi"}],
            system="You are helpful",
        ))

        call_kwargs = client._client.messages.stream.call_args[1]
        assert call_kwargs["system"] == "You are helpful"
