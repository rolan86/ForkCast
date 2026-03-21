"""Claude API client wrapper with retry, usage tracking, and multiple calling modes."""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Iterator

import anthropic

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 4096
MAX_RETRIES = 3
RETRY_DELAY = 1.0


@dataclass
class LLMResponse:
    """Standardized response from any Claude API call."""

    text: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = ""
    raw: Any = None


class ClaudeClient:
    """Wrapper around the Anthropic SDK with retry, usage tracking, and convenience methods."""

    def __init__(self, api_key: str, default_model: str = DEFAULT_MODEL):
        self._client = anthropic.Anthropic(api_key=api_key)
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Standard completion — send messages, get text back."""
        return self._call(
            messages=messages,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def tool_use(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Call with tools — Claude can return tool_use blocks."""
        return self._call(
            messages=messages,
            tools=tools,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def think(
        self,
        messages: list[dict[str, str]],
        thinking_budget: int = 10000,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> LLMResponse:
        """Extended thinking — Claude reasons step by step before responding."""
        return self._call(
            messages=messages,
            system=system,
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=1.0,  # Required for extended thinking
            thinking={"type": "enabled", "budget_tokens": thinking_budget},
        )

    def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = 1.0,
    ) -> "Iterator[StreamEvent]":
        """Stream a response, yielding StreamEvent objects."""
        from forkcast.report.models import StreamEvent

        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        with self._client.messages.stream(**kwargs) as stream:
            # Track tool block metadata keyed by id, collected from content_block_start events
            tool_index: dict[str, dict[str, Any]] = {}

            for event in stream:
                if event.type == "content_block_start":
                    cb = event.content_block
                    if cb.type == "tool_use":
                        tool_index[cb.id] = {"id": cb.id, "name": cb.name}
                elif event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        yield StreamEvent(type="text_delta", data=event.delta.text)

            final = stream.get_final_message()

            for block in final.content:
                if block.type == "tool_use":
                    # Prefer name from streaming events to avoid MagicMock `name` kwarg issue
                    tracked = tool_index.get(block.id, {})
                    name = tracked.get("name", block.name)
                    yield StreamEvent(
                        type="tool_use",
                        data={"id": block.id, "name": name, "input": block.input},
                    )

            yield StreamEvent(
                type="done",
                data={
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                    "stop_reason": final.stop_reason,
                },
            )

    def _call(self, **kwargs: Any) -> LLMResponse:
        """Internal method with retry logic."""
        messages = kwargs.pop("messages")
        system = kwargs.pop("system", None)
        tools = kwargs.pop("tools", None)
        thinking = kwargs.pop("thinking", None)

        create_kwargs: dict[str, Any] = {
            "messages": messages,
            "model": kwargs.get("model", self.default_model),
            "max_tokens": kwargs.get("max_tokens", DEFAULT_MAX_TOKENS),
        }

        if system:
            create_kwargs["system"] = system
        if tools:
            create_kwargs["tools"] = tools
        if thinking:
            create_kwargs["thinking"] = thinking
        if "temperature" in kwargs and thinking is None:
            create_kwargs["temperature"] = kwargs["temperature"]

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.messages.create(**create_kwargs)
                return self._parse_response(response)
            except anthropic.RateLimitError as e:
                last_error = e
                wait = RETRY_DELAY * (2**attempt)
                logger.warning(f"Rate limited, retrying in {wait}s (attempt {attempt + 1})")
                time.sleep(wait)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    wait = RETRY_DELAY * (2**attempt)
                    logger.warning(f"API error {e.status_code}, retrying in {wait}s")
                    time.sleep(wait)
                else:
                    raise

        raise last_error  # type: ignore[misc]

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse Anthropic API response into standardized LLMResponse."""
        text_parts = []
        tool_calls = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )
            elif block.type == "thinking":
                # Extended thinking block — captured but not included in text
                pass

        return LLMResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=getattr(response, "model", self.default_model),
            stop_reason=getattr(response, "stop_reason", ""),
            raw=response,
        )
