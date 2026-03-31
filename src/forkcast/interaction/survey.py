"""Free-text survey — concurrent agent responses + AI summary."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator, Optional

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _build_agent_system_prompt,
    _persist_message,
)
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)


def free_text_survey(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    question: str,
    agent_ids: Optional[list[int]],
    client: Any,
    domains_dir: Path,
) -> Iterator[StreamEvent]:
    """Run a free-text survey: ask all (or selected) agents, then summarize."""
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data="No profiles found")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"survey_{simulation_id}_{int(time.time())}"

    target_ids = agent_ids if agent_ids else [p.agent_id for p in profiles]
    all_responses = {}

    _persist_message(db_path, conversation_id, "user", question)

    for agent_id in target_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)
        messages = [{"role": "user", "content": question}]

        response_text = ""
        try:
            for event in client.stream(messages=messages, system=system):
                if event.type == "text_delta":
                    response_text += event.data
                    yield StreamEvent(
                        type="agent_response",
                        data={"agent_id": agent_id, "type": "text_delta", "text": event.data},
                    )
                elif event.type == "done":
                    yield StreamEvent(type="agent_done", data={"agent_id": agent_id})
        except Exception as exc:
            logger.error("Survey agent %d error: %s", agent_id, exc)

        if response_text:
            all_responses[agent_id] = response_text
            _persist_message(db_path, conversation_id, "assistant",
                             json.dumps({"agent_id": agent_id, "text": response_text}))

    # Generate AI summary
    if all_responses:
        summary_prompt = "Synthesize these survey responses into key themes (2-3 sentences):\n\n"
        for aid, text in all_responses.items():
            name = next((p.name for p in profiles if p.agent_id == aid), f"Agent {aid}")
            summary_prompt += f"**{name}:** {text}\n\n"

        try:
            summary_resp = client.complete(
                messages=[{"role": "user", "content": summary_prompt}],
                system="You are a research analyst summarizing survey responses. Be concise.",
            )
            yield StreamEvent(type="summary", data={"text": summary_resp.text})
        except Exception as exc:
            logger.error("Summary generation error: %s", exc)

    yield StreamEvent(type="complete", data={})
