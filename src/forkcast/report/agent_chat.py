"""Agent chat function — in-character conversation with a simulation agent."""

import json
import logging
from pathlib import Path
from typing import Any, Iterator

from jinja2 import Template

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.report.models import StreamEvent
from forkcast.simulation.models import AgentProfile

logger = logging.getLogger(__name__)


def _load_profiles(profiles_path: Path) -> list[AgentProfile]:
    """Load agent profiles from agents.json."""
    if not profiles_path.exists():
        logger.warning("Profiles file not found: %s", profiles_path)
        return []
    try:
        raw = json.loads(profiles_path.read_text(encoding="utf-8"))
        profiles = []
        for item in raw:
            profiles.append(
                AgentProfile(
                    agent_id=item["agent_id"],
                    name=item["name"],
                    username=item["username"],
                    bio=item["bio"],
                    persona=item["persona"],
                    age=item["age"],
                    gender=item["gender"],
                    profession=item["profession"],
                    interests=item.get("interests", []),
                    entity_type=item.get("entity_type", "Person"),
                    entity_source=item.get("entity_source", ""),
                )
            )
        return profiles
    except Exception as exc:
        logger.warning("Could not load profiles: %s", exc)
        return []


def _load_agent_actions(db_path: Path, simulation_id: str, agent_id: int) -> list[dict[str, Any]]:
    """Load CREATE_POST and CREATE_COMMENT actions for a specific agent."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT action_type, content, round, timestamp "
            "FROM simulation_actions "
            "WHERE simulation_id = ? AND agent_id = ? "
            "AND action_type IN ('CREATE_POST', 'CREATE_COMMENT') "
            "ORDER BY round ASC, timestamp ASC",
            (simulation_id, agent_id),
        ).fetchall()
    return [dict(row) for row in rows]


def _load_chat_history(db_path: Path, conversation_id: str) -> list[dict[str, Any]]:
    """Load prior messages for a conversation from chat_history."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT role, message FROM chat_history WHERE conversation_id = ? ORDER BY id ASC",
            (conversation_id,),
        ).fetchall()
    return [{"role": row["role"], "content": row["message"]} for row in rows]


def _persist_message(db_path: Path, conversation_id: str, role: str, message: str) -> None:
    """Persist a single chat message to chat_history."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO chat_history (conversation_id, role, message) VALUES (?, ?, ?)",
            (conversation_id, role, message),
        )


def _build_agent_system_prompt(
    profile: AgentProfile,
    actions: list[dict[str, Any]],
    domains_dir: Path,
) -> str:
    """Render the agent_system Jinja2 template and inject agent's own actions."""
    try:
        domain = load_domain("_default", domains_dir)
        system_template_text = read_prompt(domain, "agent_system")
    except Exception as exc:
        logger.warning("Could not load agent_system prompt: %s — using fallback", exc)
        system_template_text = (
            "You are {{ agent_name }} (@{{ username }}). {{ persona }}\n"
            "Age: {{ age }}, Gender: {{ gender }}, Profession: {{ profession }}.\n"
            "Interests: {{ interests }}."
        )

    template = Template(system_template_text)
    system_prompt = template.render(
        agent_name=profile.name,
        username=profile.username,
        bio=profile.bio,
        persona=profile.persona,
        age=profile.age,
        gender=profile.gender,
        profession=profile.profession,
        interests=", ".join(profile.interests) if profile.interests else "",
    )

    # Inject agent's own posts/comments as memory
    if actions:
        action_lines: list[str] = []
        for action in actions:
            try:
                content_data = json.loads(action["content"] or "{}")
                text = content_data.get("content", action["content"] or "")
            except (json.JSONDecodeError, TypeError):
                text = action["content"] or ""

            action_lines.append(
                f"- [Round {action['round']}] {action['action_type']}: {text}"
            )

        actions_block = "\n".join(action_lines)
        system_prompt = (
            system_prompt
            + f"\n\n## Your Activity in the Simulation\n\n{actions_block}\n"
        )

    return system_prompt


def agent_chat(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    agent_id: int,
    message: str,
    client: Any,
    domains_dir: Path,
) -> Iterator[StreamEvent]:
    """
    In-character conversation with a simulation agent.

    Loads the agent profile from agents.json, builds a system prompt from the
    agent_system template (with the agent's own simulation actions injected),
    and streams a response. No tools are used.

    Uses conversation_id = f"agent_chat_{simulation_id}_{agent_id}".
    Persists user and assistant messages to chat_history.

    Yields a single error StreamEvent if the agent is not found.
    """
    conversation_id = f"agent_chat_{simulation_id}_{agent_id}"

    # --- Load agent profile ---
    sim_dir = data_dir / simulation_id
    profiles_path = sim_dir / "profiles" / "agents.json"
    profiles = _load_profiles(profiles_path)

    profile: AgentProfile | None = None
    for p in profiles:
        if p.agent_id == agent_id:
            profile = p
            break

    if profile is None:
        yield StreamEvent(type="error", data=f"Agent {agent_id} not found in simulation {simulation_id!r}")
        return

    # --- Load agent's own actions ---
    actions = _load_agent_actions(db_path, simulation_id, agent_id)

    # --- Build system prompt ---
    system_prompt = _build_agent_system_prompt(profile, actions, domains_dir)

    # --- Load prior chat history ---
    prior_messages = _load_chat_history(db_path, conversation_id)

    # --- Persist user message ---
    _persist_message(db_path, conversation_id, "user", message)

    # Build message list
    messages: list[dict[str, Any]] = prior_messages + [
        {"role": "user", "content": message}
    ]

    # --- Stream response (no tools for agent chat) ---
    response_parts: list[str] = []

    for event in client.stream(messages=messages, system=system_prompt):
        if event.type == "text_delta":
            yield event
            response_parts.append(str(event.data))
        elif event.type == "done":
            yield event
        # Ignore other event types (tool_use should not appear without tools)

    # --- Persist assistant message ---
    final_text = "".join(response_parts)
    _persist_message(db_path, conversation_id, "assistant", final_text)
