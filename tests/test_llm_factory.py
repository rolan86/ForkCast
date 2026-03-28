"""Tests for the LLM client factory."""

from unittest.mock import patch

import pytest


def test_create_claude_client():
    """Factory creates ClaudeClient for 'claude' provider."""
    from forkcast.llm.factory import create_llm_client
    from forkcast.llm.client import ClaudeClient

    with patch("anthropic.Anthropic"):
        client = create_llm_client(provider="claude", api_key="sk-test-123")
    assert isinstance(client, ClaudeClient)


def test_create_ollama_client():
    """Factory creates OllamaClient for 'ollama' provider."""
    from forkcast.llm.factory import create_llm_client
    from forkcast.llm.ollama_client import OllamaClient

    with patch("openai.OpenAI"):
        client = create_llm_client(provider="ollama")
    assert isinstance(client, OllamaClient)
    assert client.default_model == "llama3.1"


def test_create_ollama_custom_model():
    """Factory passes custom model to OllamaClient."""
    from forkcast.llm.factory import create_llm_client

    with patch("openai.OpenAI"):
        client = create_llm_client(provider="ollama", ollama_model="mistral")
    assert client.default_model == "mistral"


def test_claude_requires_api_key():
    """Factory raises ValueError when Claude provider has no API key."""
    from forkcast.llm.factory import create_llm_client

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        create_llm_client(provider="claude", api_key="")


def test_unknown_provider():
    """Factory raises ValueError for unknown provider."""
    from forkcast.llm.factory import create_llm_client

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_client(provider="gpt")
