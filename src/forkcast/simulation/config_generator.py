"""Generate simulation configuration using Claude extended thinking."""

import json
import logging
from typing import Any

from jinja2 import Template

from forkcast.llm.client import ClaudeClient
from forkcast.llm.utils import strip_code_fences
from forkcast.simulation.models import AgentProfile, SimulationConfig

logger = logging.getLogger(__name__)


def _build_config_prompt(
    profiles: list[AgentProfile],
    requirement: str,
    config_template: str,
) -> str:
    """Build the config generation prompt using the domain template."""
    entities_summary = "\n".join(
        f"- {p.name} ({p.entity_type}): {p.profession}, interests: {', '.join(p.interests)}"
        for p in profiles
    )
    template = Template(config_template)
    return template.render(
        entities_summary=entities_summary,
        requirement=requirement,
    )


def _clamp(value: int | float, minimum: int | float, maximum: int | float) -> int | float:
    """Clamp a value between minimum and maximum bounds."""
    return max(minimum, min(maximum, value))


def generate_config(
    client: ClaudeClient,
    profiles: list[AgentProfile],
    requirement: str,
    config_template: str,
    model: str | None = None,
) -> tuple[SimulationConfig, dict[str, int]]:
    """Generate simulation config using extended thinking.

    Returns (SimulationConfig, {"input": N, "output": N}).
    """
    prompt = _build_config_prompt(
        profiles=profiles,
        requirement=requirement,
        config_template=config_template,
    )

    system = (
        "You are generating simulation parameters for a collective intelligence simulation. "
        "Think carefully about timing, agent behavior, and platform dynamics. "
        "Return ONLY valid JSON matching the requested schema. "
        "No markdown formatting. No code fences."
    )

    response = client.smart_call(
        model=model or client.default_model,
        messages=[{"role": "user", "content": prompt}],
        system=system,
        thinking_budget=10000,
    )

    data = json.loads(strip_code_fences(response.text))

    config = SimulationConfig(
        total_hours=int(_clamp(data.get("total_hours", 48), 12, 168)),
        minutes_per_round=int(_clamp(data.get("minutes_per_round", 30), 15, 60)),
        peak_hours=data.get("peak_hours", [9, 10, 11, 12, 17, 18, 19]),
        off_peak_hours=data.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
        peak_multiplier=float(_clamp(data.get("peak_multiplier", 1.5), 1.0, 3.0)),
        off_peak_multiplier=float(_clamp(data.get("off_peak_multiplier", 0.3), 0.1, 1.0)),
        seed_posts=data.get("seed_posts", []),
        hot_topics=data.get("hot_topics", []),
        narrative_direction=data.get("narrative_direction", ""),
        agent_configs=data.get("agent_configs", []),
        platform_config=data.get("platform_config", {}),
    )

    tokens = {"input": response.input_tokens, "output": response.output_tokens}
    return config, tokens
