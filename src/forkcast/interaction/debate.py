"""Agent-to-agent debate — alternating rounds with optional moderation."""

import json
import logging
import time
from pathlib import Path
from typing import Any, Iterator

from forkcast.db.queries import get_domain_for_simulation
from forkcast.report.agent_chat import (
    _load_profiles,
    _load_agent_actions,
    _build_agent_system_prompt,
    _persist_message,
)
from forkcast.report.models import StreamEvent

logger = logging.getLogger(__name__)

ROUND_LABELS = {
    1: "Opening Statements",
    2: "Rebuttals",
    3: "Cross-Examination",
    4: "Final Arguments",
    5: "Closing Statements",
}


def run_debate(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    agent_id_pro: int,
    agent_id_con: int,
    topic: str,
    rounds: int,
    mode: str,  # "autoplay" or "moderated"
    client: Any,
    domains_dir: Path,
    interjection: str = "",
    debate_history: list[dict] | None = None,
    current_round: int = 1,
) -> Iterator[StreamEvent]:
    """Run a debate between two agents.

    For autoplay: runs all rounds and streams events.
    For moderated: runs one round pair and returns.
    """
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)
    if not profiles:
        yield StreamEvent(type="error", data="No profiles found")
        return

    pro = next((p for p in profiles if p.agent_id == agent_id_pro), None)
    con = next((p for p in profiles if p.agent_id == agent_id_con), None)
    if not pro or not con:
        yield StreamEvent(type="error", data="Debate agents not found")
        return

    domain_name = get_domain_for_simulation(db_path, simulation_id)
    conversation_id = f"debate_{simulation_id}_{int(time.time())}"
    history = debate_history or []

    pro_actions = _load_agent_actions(db_path, simulation_id, agent_id_pro)
    con_actions = _load_agent_actions(db_path, simulation_id, agent_id_con)
    pro_base_system = _build_agent_system_prompt(pro, pro_actions, domains_dir, domain_name)
    con_base_system = _build_agent_system_prompt(con, con_actions, domains_dir, domain_name)

    def _debate_system(base_system: str, side: str) -> str:
        return (
            f"{base_system}\n\n"
            f"## Debate Context\n"
            f"Topic: {topic}\n"
            f"Your position: {side.upper()}\n"
            f"Argue passionately from your position. Stay in character.\n"
            f"Keep responses to 2-3 paragraphs."
        )

    pro_system = _debate_system(pro_base_system, "pro")
    con_system = _debate_system(con_base_system, "con")

    start = current_round
    end = rounds + 1 if mode == "autoplay" else current_round + 1

    for round_num in range(start, end):
        label = ROUND_LABELS.get(round_num, f"Round {round_num}")
        yield StreamEvent(type="round_start", data={"round": round_num, "label": label})

        # Pro speaks
        pro_messages = _build_debate_messages(history, "pro", interjection if round_num == start else "")
        pro_text = ""
        for event in client.stream(messages=pro_messages, system=pro_system):
            if event.type == "text_delta":
                pro_text += event.data
                yield StreamEvent(
                    type="agent_response",
                    data={"agent_id": agent_id_pro, "side": "pro", "type": "text_delta", "text": event.data},
                )
            elif event.type == "done":
                yield StreamEvent(type="agent_done", data={"agent_id": agent_id_pro, "side": "pro"})

        history.append({"round": round_num, "side": "pro", "agent_id": agent_id_pro, "text": pro_text})

        # Con speaks
        con_messages = _build_debate_messages(history, "con", "")
        con_text = ""
        for event in client.stream(messages=con_messages, system=con_system):
            if event.type == "text_delta":
                con_text += event.data
                yield StreamEvent(
                    type="agent_response",
                    data={"agent_id": agent_id_con, "side": "con", "type": "text_delta", "text": event.data},
                )
            elif event.type == "done":
                yield StreamEvent(type="agent_done", data={"agent_id": agent_id_con, "side": "con"})

        history.append({"round": round_num, "side": "con", "agent_id": agent_id_con, "text": con_text})

        yield StreamEvent(type="round_end", data={"round": round_num})

        # Persist both responses
        _persist_message(db_path, conversation_id, "assistant",
                         json.dumps({"round": round_num, "pro": pro_text, "con": con_text}))

    yield StreamEvent(type="complete", data={})


def _build_debate_messages(history: list[dict], current_side: str, interjection: str) -> list[dict]:
    """Build message history for a debate participant."""
    messages = []
    for entry in history:
        role = "assistant" if entry["side"] == current_side else "user"
        messages.append({"role": role, "content": entry["text"]})

    if interjection:
        messages.append({"role": "user", "content": f"[Moderator]: {interjection}"})
    elif not messages:
        messages.append({"role": "user", "content": "Please make your opening statement."})
    else:
        messages.append({"role": "user", "content": "Please respond to the previous argument."})

    return messages
