"""Structured poll — agents pick from options with reasoning."""

import json
import logging
from pathlib import Path
from typing import Any, Optional

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _build_agent_system_prompt,
    _load_agent_actions,
)

logger = logging.getLogger(__name__)


def structured_poll(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    question: str,
    options: list[str],
    agent_ids: Optional[list[int]],
    client: Any,
    domains_dir: Path,
) -> dict:
    """Run a structured poll. Returns results with choices, reasoning, and summary counts."""
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        return {"results": [], "summary": {}}

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    target_ids = agent_ids if agent_ids else [p.agent_id for p in profiles]

    options_str = "\n".join(f"  {i+1}. {opt}" for i, opt in enumerate(options))
    results = []

    for agent_id in target_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)

        poll_prompt = (
            f"Question: {question}\n\nOptions:\n{options_str}\n\n"
            "Pick ONE option and explain briefly. Reply as JSON: "
            '{"choice": "<exact option text>", "reasoning": "<1-2 sentences>"}'
        )

        try:
            response = client.complete(
                messages=[{"role": "user", "content": poll_prompt}],
                system=system,
            )
            parsed = json.loads(response.text)
            results.append({
                "agent_id": agent_id,
                "choice": parsed.get("choice", options[0]),
                "reasoning": parsed.get("reasoning", ""),
            })
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Poll agent %d error: %s", agent_id, exc)
            results.append({
                "agent_id": agent_id,
                "choice": "Error",
                "reasoning": str(exc),
            })

    # Build summary counts
    summary = {}
    for opt in options:
        summary[opt] = sum(1 for r in results if r["choice"] == opt)

    return {"results": results, "summary": summary}
