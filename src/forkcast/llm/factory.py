"""LLM client factory — creates the right client based on provider config."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forkcast.llm.client import LLMClient

PROVIDERS = ("claude", "ollama")


def create_llm_client(
    provider: str = "claude",
    api_key: str = "",
    ollama_base_url: str = "http://localhost:11434/v1",
    ollama_model: str = "llama3.1",
    default_model: str = "claude-sonnet-4-6",
) -> LLMClient:
    """Create an LLM client for the specified provider."""
    if provider == "claude":
        if not api_key:
            raise ValueError("Claude requires ANTHROPIC_API_KEY")
        from forkcast.llm.client import ClaudeClient
        return ClaudeClient(api_key=api_key, default_model=default_model)
    elif provider == "ollama":
        from forkcast.llm.ollama_client import OllamaClient
        return OllamaClient(base_url=ollama_base_url, default_model=ollama_model)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}. Choose from: {PROVIDERS}")
