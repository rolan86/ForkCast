"""Panel interaction -- concurrent multi-agent Q&A."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator

from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _persist_message,
    _build_agent_system_prompt,
)
from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)


def panel_interview(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    agent_ids: list[int],
    question: str,
    client: Any,
    domains_dir: Path,
) -> Iterator[StreamEvent]:
    """Run a panel interview: ask the same question to multiple agents sequentially.

    Yields StreamEvent with types: agent_response, agent_done, complete, error.
    agent_response data includes agent_id for frontend routing.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data=f"No profiles found for simulation {simulation_id}")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"panel_{simulation_id}_{int(time.time())}"

    # Persist the user question once for the panel
    _persist_message(db_path, conversation_id, "user", question)

    for agent_id in agent_ids:
        profile = next((p for p in profiles if p.agent_id == agent_id), None)
        if profile is None:
            yield StreamEvent(type="error", data=f"Agent {agent_id} not found")
            continue

        actions = _load_agent_actions(db_path, simulation_id, agent_id)
        system = _build_agent_system_prompt(profile, actions, domains_dir, domain_name)
        messages = [{"role": "user", "content": question}]

        full_response = ""
        try:
            for event in client.stream(messages=messages, system=system):
                if event.type == "text_delta":
                    full_response += event.data
                    yield StreamEvent(
                        type="agent_response",
                        data={"agent_id": agent_id, "type": "text_delta", "text": event.data},
                    )
                elif event.type == "done":
                    yield StreamEvent(type="agent_done", data={"agent_id": agent_id})
        except Exception as exc:
            logger.error("Panel agent %d error: %s", agent_id, exc)
            yield StreamEvent(type="error", data=f"Agent {agent_id} error: {exc}")

        if full_response:
            _persist_message(db_path, conversation_id, "assistant",
                             json.dumps({"agent_id": agent_id, "text": full_response}))

    yield StreamEvent(type="complete", data={})
