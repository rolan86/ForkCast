"""Report chat function — interactive Q&A with a completed report using tool-use loop."""

import json
import logging
from pathlib import Path
from typing import Any, Iterator

import networkx as nx

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.graph.graph_store import load_graph
from forkcast.report.models import StreamEvent, ToolContext
from forkcast.report.tools import REPORT_TOOLS, execute_tool

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_ROUNDS = 3


def _load_profiles_for_chat(profiles_path: Path) -> list:
    """Load agent profiles from agents.json; return empty list if absent."""
    if not profiles_path.exists():
        return []
    try:
        from forkcast.simulation.models import AgentProfile

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


def _load_graph_optional(graph_path: Path) -> nx.DiGraph:
    """Load graph from disk; return empty DiGraph if missing."""
    if graph_path.exists():
        try:
            return load_graph(graph_path)
        except Exception as exc:
            logger.warning("Could not load graph: %s", exc)
    return nx.DiGraph()


def _load_chroma_optional(chroma_dir: Path) -> Any:
    """Load ChromaDB collection if available; return None otherwise."""
    if not chroma_dir.exists():
        return None
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(chroma_dir))
        collections = client.list_collections()
        if collections:
            return client.get_collection(collections[0].name)
        return None
    except Exception as exc:
        logger.warning("Could not load ChromaDB: %s", exc)
        return None


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


def report_chat(
    db_path: Path,
    data_dir: Path,
    report_id: str,
    message: str,
    client: Any,
    domains_dir: Path,
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
) -> Iterator[StreamEvent]:
    """
    Interactive chat with a completed report using a tool-use loop.

    Loads the report from DB, builds context, runs tool-use loop (up to
    max_tool_rounds), and yields StreamEvent objects. Persists user and
    assistant messages to chat_history using report_id as conversation_id.

    Yields a single error StreamEvent if the report is not found.
    """
    # --- Load report from DB ---
    with get_db(db_path) as conn:
        report_row = conn.execute(
            "SELECT r.*, s.id as sim_id, s.project_id "
            "FROM reports r JOIN simulations s ON r.simulation_id = s.id "
            "WHERE r.id = ?",
            (report_id,),
        ).fetchone()

    if report_row is None:
        yield StreamEvent(type="error", data=f"Report not found: {report_id!r}")
        return

    simulation_id = report_row["sim_id"]
    project_id = report_row["project_id"]
    report_markdown = report_row["content_markdown"] or ""

    # --- Load context ---
    sim_dir = data_dir / simulation_id
    profiles_path = sim_dir / "profiles" / "agents.json"
    graph_path = sim_dir / "graph.json"
    chroma_dir = sim_dir / "chroma"

    profiles = _load_profiles_for_chat(profiles_path)
    graph = _load_graph_optional(graph_path)
    chroma_collection = _load_chroma_optional(chroma_dir)

    # --- Load domain guidelines ---
    try:
        domain = load_domain("_default", domains_dir)
        guidelines = read_prompt(domain, "report_guidelines")
    except Exception as exc:
        logger.warning("Could not load report_guidelines: %s — using fallback", exc)
        guidelines = "You are a report analyst. Answer questions about the report."

    # --- Build system prompt with report content ---
    system_prompt = (
        f"{guidelines}\n\n"
        f"## Report\n\n{report_markdown}\n"
    )

    # --- Build tool context ---
    ctx = ToolContext(
        db_path=db_path,
        simulation_id=simulation_id,
        project_id=project_id,
        data_dir=data_dir,
        graph=graph,
        chroma_collection=chroma_collection,
        profiles=profiles,
        client=client,
        domains_dir=domains_dir,
    )

    # --- Load prior chat history ---
    prior_messages = _load_chat_history(db_path, report_id)

    # --- Persist user message ---
    _persist_message(db_path, report_id, "user", message)

    # Build message list: history + current user message
    messages: list[dict[str, Any]] = prior_messages + [
        {"role": "user", "content": message}
    ]

    # --- Tool-use loop ---
    all_response_parts: list[str] = []

    for _round in range(max_tool_rounds + 1):
        events = list(client.stream(
            messages=messages,
            system=system_prompt,
            tools=REPORT_TOOLS,
        ))

        # Yield text events to caller and collect text
        round_text_parts: list[str] = []
        stop_reason = "end_turn"
        tool_use_events: list[dict[str, Any]] = []

        for event in events:
            if event.type == "text_delta":
                yield event
                round_text_parts.append(str(event.data))
            elif event.type == "tool_use":
                tool_use_events.append(event.data)
            elif event.type == "done":
                stop_reason = event.data.get("stop_reason", "end_turn") if isinstance(event.data, dict) else "end_turn"
                yield event

        round_text = "".join(round_text_parts)
        all_response_parts.append(round_text)

        # Build assistant message content
        assistant_content: list[dict[str, Any]] | str
        if tool_use_events:
            assistant_content = []
            if round_text:
                assistant_content.append({"type": "text", "text": round_text})
            for tc in tool_use_events:
                assistant_content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": tc["input"],
                })
        else:
            assistant_content = round_text

        messages.append({"role": "assistant", "content": assistant_content})

        # If no tool calls or not a tool_use stop, we're done
        if stop_reason != "tool_use" or not tool_use_events:
            break

        # Execute tool calls
        if _round >= max_tool_rounds:
            # Exceeded max rounds — stop
            logger.warning("Max tool rounds (%d) reached for report chat %r", max_tool_rounds, report_id)
            break

        tool_results: list[dict[str, Any]] = []
        for tc in tool_use_events:
            tool_name = tc["name"]
            tool_input = tc["input"]
            tool_id = tc["id"]

            logger.debug("report_chat: executing tool %r", tool_name)
            try:
                result = execute_tool(ctx, tool_name, tool_input)
            except Exception as exc:
                logger.error("Tool %r failed: %s", tool_name, exc)
                result = {"error": str(exc)}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": json.dumps(result, default=str),
            })

        messages.append({"role": "user", "content": tool_results})

    # --- Persist assistant message ---
    final_text = "".join(all_response_parts)
    _persist_message(db_path, report_id, "assistant", final_text)
