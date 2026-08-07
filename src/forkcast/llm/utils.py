"""Shared LLM response parsing utilities."""

import re

_THINKING_RE = re.compile(r"<thinking>.*?</thinking>", re.DOTALL)


def strip_code_fences(text: str) -> str:
    """Strip markdown code fences and thinking blocks from LLM response text."""
    # Remove <thinking>...</thinking> blocks
    text = _THINKING_RE.sub("", text)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
    return text
