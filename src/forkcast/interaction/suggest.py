"""Smart agent suggestions — rank agents by relevance to a topic."""

import json
import logging
from pathlib import Path
from typing import Any

from forkcast.report.agent_chat import _load_profiles

logger = logging.getLogger(__name__)


def suggest_agents(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    topic: str,
    client: Any,
) -> dict:
    """Rank agents by relevance to the given topic.

    Returns {"suggestions": [{"agent_id": int, "reason": str}, ...]}.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        return {"suggestions": []}

    profiles_summary = "\n".join(
        f"- Agent {p.agent_id}: {p.name} — {p.profession}. "
        f"Interests: {', '.join(p.interests)}. Bio: {p.bio}"
        for p in profiles
    )

    system = (
        "You rank simulation agents by relevance to a topic. "
        'Return JSON: {"suggestions": [{"agent_id": <int>, "reason": "<one line>"}]}. '
        "Rank most relevant first. Include all agents."
    )
    messages = [
        {"role": "user", "content": f"Topic: {topic}\n\nAgents:\n{profiles_summary}"}
    ]

    try:
        response = client.complete(messages=messages, system=system)
        return json.loads(response.text)
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Suggest agents failed: %s", exc)
        # Fallback: return all agents unranked
        return {
            "suggestions": [
                {"agent_id": p.agent_id, "reason": f"{p.profession} — {p.bio[:50]}"}
                for p in profiles
            ]
        }
