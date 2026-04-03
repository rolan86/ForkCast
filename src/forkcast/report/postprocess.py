"""Report post-processor — extract structured data from report markdown."""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from forkcast.domains.loader import DomainConfig

logger = logging.getLogger(__name__)

# Pattern to strip markdown code fences (common with Ollama models)
_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def postprocess_report(
    content_markdown: str,
    domain: DomainConfig,
    client,
) -> dict | None:
    """Extract structured data from report markdown using domain's post_process prompt.

    Returns parsed JSON dict if domain has post_process prompt, None otherwise.
    Uses whichever LLM provider is configured (Claude or Ollama).
    """
    if "post_process" not in domain.prompts:
        return None

    prompt_path = domain.prompts["post_process"]
    post_process_prompt = prompt_path.read_text(encoding="utf-8")

    response = client.complete(
        messages=[{"role": "user", "content": content_markdown}],
        system=post_process_prompt,
    )

    raw_text = response.text.strip()

    # Strip markdown code fences if present
    fence_match = _FENCE_RE.match(raw_text)
    if fence_match:
        raw_text = fence_match.group(1).strip()

    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.warning("Post-process JSON parse failed: %s — raw: %.200s", exc, raw_text)
        return None
