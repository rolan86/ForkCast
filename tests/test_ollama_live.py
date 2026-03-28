"""Live integration tests for OllamaClient — requires a running Ollama instance.

Run manually: pytest tests/test_ollama_live.py -v --no-header -rN
These tests are skipped by default in CI.
"""

import pytest

pytestmark = pytest.mark.skip(reason="requires local Ollama running on localhost:11434")


def test_live_complete():
    """Basic completion against real Ollama."""
    from forkcast.llm.ollama_client import OllamaClient
    client = OllamaClient()
    result = client.complete(messages=[{"role": "user", "content": "Say hello in one word."}])
    assert result.text
    assert result.output_tokens > 0


def test_live_stream():
    """Streaming against real Ollama."""
    from forkcast.llm.ollama_client import OllamaClient
    client = OllamaClient()
    events = list(client.stream(messages=[{"role": "user", "content": "Count to 3."}]))
    text_events = [e for e in events if e.type == "text_delta"]
    done_events = [e for e in events if e.type == "done"]
    assert len(text_events) > 0
    assert len(done_events) == 1


def test_live_think_degrades():
    """think() works via graceful degradation."""
    from forkcast.llm.ollama_client import OllamaClient
    client = OllamaClient()
    result = client.think(messages=[{"role": "user", "content": "What is 2+2?"}])
    assert result.text
