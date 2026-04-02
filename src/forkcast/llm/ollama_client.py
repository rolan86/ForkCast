"""Ollama LLM client using OpenAI-compatible API."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Iterator

import openai

from forkcast.llm.client import LLMResponse, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)


class OllamaClient:
    """LLM client for Ollama via OpenAI-compatible /v1 endpoint."""

    def __init__(self, base_url: str = "http://localhost:11434/v1", default_model: str = "llama3.1"):
        self.default_model = default_model
        self._base_url = base_url
        self._client = openai.OpenAI(base_url=base_url, api_key="ollama")

    def complete(
        self,
        messages: list[dict[str, str]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ) -> LLMResponse:
        """Standard completion."""
        return self._call(
            messages=self._prepend_system(messages, system),
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
        max_tokens: int = 4096,
        temperature: float = 1.0,
        **kwargs: Any,
    ) -> LLMResponse:
        """Call with tools, falling back to structured prompting if unsupported."""
        openai_tools = self._translate_tools(tools)
        try:
            response = self._call(
                messages=self._prepend_system(messages, system),
                model=model or self.default_model,
                max_tokens=max_tokens,
                temperature=temperature,
                tools=openai_tools,
            )
            # If tools were requested but none returned, try structured fallback
            if not response.tool_calls and tools:
                return self._structured_tool_fallback(messages, tools, system, model, max_tokens, temperature)
            # Validate tool call has the required keys from the schema
            if response.tool_calls and tools and not self._validate_tool_response(response.tool_calls, tools):
                logger.info("Native tool call has wrong keys, falling back to structured prompting")
                return self._structured_tool_fallback(messages, tools, system, model, max_tokens, temperature)
            return response
        except openai.BadRequestError as e:
            if "does not support tools" in str(e) or "tool_use is not supported" in str(e):
                logger.info("Model does not support tools, falling back to structured prompting")
                return self._structured_tool_fallback(messages, tools, system, model, max_tokens, temperature)
            raise

    def think(
        self,
        messages: list[dict[str, str]],
        thinking_budget: int = 10000,
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 16000,
    ) -> LLMResponse:
        """No extended thinking — delegates to complete()."""
        logger.debug("Ollama does not support extended thinking, delegating to complete()")
        return self.complete(messages=messages, system=system, model=model, max_tokens=max_tokens)

    def smart_call(
        self,
        model: str,
        messages: list[dict[str, str]],
        system: str | None = None,
        thinking_budget: int = 8000,
        **kwargs,
    ) -> LLMResponse:
        """Always routes to complete() — no Ollama model supports thinking."""
        return self.complete(messages=messages, system=system, model=model, **kwargs)

    def stream(
        self,
        messages: list[dict[str, Any]],
        system: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 1.0,
    ) -> Iterator:
        """Stream a response, yielding StreamEvent objects."""
        from forkcast.report.models import StreamEvent

        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": self._prepend_system(messages, system),
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = self._translate_tools(tools)

        try:
            stream = self._client.chat.completions.create(**kwargs)
        except openai.APIConnectionError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self._base_url}. "
                "Is Ollama running? Start it with: ollama serve"
            )

        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                yield StreamEvent(type="text_delta", data=delta.content)

        yield StreamEvent(type="done", data={"stop_reason": "end_turn"})

    # --- Private helpers ---

    def _prepend_system(self, messages: list[dict], system: str | None) -> list[dict]:
        """Prepend system message and translate Anthropic-format messages to OpenAI format."""
        translated = []
        for msg in messages:
            translated.extend(self._translate_message(msg))
        if system:
            return [{"role": "system", "content": system}] + translated
        return translated

    def _translate_message(self, msg: dict) -> list[dict]:
        """Translate a single message from Anthropic to OpenAI format if needed."""
        role = msg.get("role", "user")
        content = msg.get("content")

        # String content — pass through
        if isinstance(content, str):
            return [{"role": role, "content": content}]

        # List content — could be Anthropic content blocks or tool results
        if isinstance(content, list):
            # Check if these are Anthropic tool_result blocks
            if content and isinstance(content[0], dict) and content[0].get("type") == "tool_result":
                results = []
                for block in content:
                    results.append({
                        "role": "tool",
                        "tool_call_id": block.get("tool_use_id", "unknown"),
                        "content": block.get("content", ""),
                    })
                return results

            # Check if these are Anthropic content blocks (text + tool_use)
            if content and isinstance(content[0], dict):
                # Extract text and tool calls from assistant content blocks
                text_parts = []
                tool_calls = []
                for block in content:
                    block_type = getattr(block, "type", None) or block.get("type", "")
                    if block_type == "text":
                        text_parts.append(getattr(block, "text", None) or block.get("text", ""))
                    elif block_type == "tool_use":
                        tc_id = getattr(block, "id", None) or block.get("id", "unknown")
                        tc_name = getattr(block, "name", None) or block.get("name", "")
                        tc_input = getattr(block, "input", None) or block.get("input", {})
                        tool_calls.append({
                            "id": tc_id,
                            "type": "function",
                            "function": {
                                "name": tc_name,
                                "arguments": json.dumps(tc_input) if isinstance(tc_input, dict) else str(tc_input),
                            },
                        })

                result: dict[str, Any] = {"role": role, "content": "\n".join(text_parts) if text_parts else ""}
                if tool_calls:
                    result["tool_calls"] = tool_calls
                return [result]

        # Fallback — pass through as-is
        return [{"role": role, "content": str(content) if content else ""}]

    def _translate_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Translate Anthropic tool schema to OpenAI function-calling format."""
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "parameters": t.get("input_schema", {}),
                },
            }
            for t in tools
        ]

    def _validate_tool_response(self, tool_calls: list[dict], tools: list[dict]) -> bool:
        """Check that tool call responses contain the required keys from the tool schema."""
        tool_schemas = {t["name"]: t.get("input_schema", {}) for t in tools}
        for tc in tool_calls:
            schema = tool_schemas.get(tc.get("name", ""), {})
            required_keys = set(schema.get("required", []))
            if required_keys and not required_keys.issubset(set(tc.get("input", {}).keys())):
                return False
        return True

    def _structured_tool_fallback(
        self, messages, tools, system, model, max_tokens, temperature
    ) -> LLMResponse:
        """Fall back to structured prompting when native tool use unavailable."""
        tool_sections = []
        for i, t in enumerate(tools):
            schema = t.get("input_schema", {})
            schema_str = json.dumps(schema, indent=2)
            tool_sections.append(
                f"{i+1}. **{t['name']}**: {t.get('description', '')}\n"
                f"   Expected JSON schema for \"input\":\n"
                f"   ```json\n   {schema_str}\n   ```"
            )
        tool_block = "\n\n".join(tool_sections)

        fallback_system = (
            f"{system or ''}\n\n"
            f"You have these tools available:\n\n{tool_block}\n\n"
            "IMPORTANT: To use a tool, respond with ONLY a valid JSON object in this exact format:\n"
            '{"name": "tool_name", "input": {<your data matching the schema above>}}\n\n'
            "The \"input\" field MUST match the JSON schema shown above for the tool you choose. "
            "Do not include any other text before or after the JSON."
        ).strip()

        response = self.complete(
            messages=messages,
            system=fallback_system,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        # Try to parse tool call from response text
        text = response.text.strip()
        # Strip markdown code fences if present (common with smaller models)
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        # Extract JSON object if surrounded by extra text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start:end + 1]
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "name" in parsed:
                response.tool_calls = [{
                    "id": "fallback_1",
                    "name": parsed["name"],
                    "input": parsed.get("input", {}),
                }]
                response.text = ""
        except (json.JSONDecodeError, KeyError):
            pass  # Return as plain text if not parseable

        return response

    def _call(self, **kwargs: Any) -> LLMResponse:
        """Internal method with retry logic."""
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.chat.completions.create(**kwargs)
                return self._parse_response(response)
            except openai.APIConnectionError:
                raise ConnectionError(
                    f"Cannot connect to Ollama at {self._base_url}. "
                    "Is Ollama running? Start it with: ollama serve"
                )
            except openai.BadRequestError:
                raise  # Don't retry bad requests — caller handles these
            except openai.APIError as e:
                last_error = e
                wait = RETRY_DELAY * (2 ** attempt)
                logger.warning(f"Ollama API error, retrying in {wait}s (attempt {attempt + 1}): {e}")
                time.sleep(wait)

        raise last_error  # type: ignore[misc]

    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse OpenAI API response into LLMResponse."""
        choice = response.choices[0]
        text = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                })

        return LLMResponse(
            text=text,
            tool_calls=tool_calls,
            input_tokens=getattr(response.usage, "prompt_tokens", 0),
            output_tokens=getattr(response.usage, "completion_tokens", 0),
            model=getattr(response, "model", self.default_model),
            stop_reason=choice.finish_reason or "",
            raw=response,
        )
