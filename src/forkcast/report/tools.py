"""Report agent tool implementations and schemas."""

import json
import logging
from collections import deque
from typing import Any

from jinja2 import Template

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.report.models import ToolContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool schemas (Claude tool-use format)
# ---------------------------------------------------------------------------

REPORT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "graph_search",
        "description": (
            "Semantic search over the knowledge graph using vector embeddings. "
            "Returns the most relevant entities, facts, or relationships matching the query."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "graph_explore",
        "description": (
            "Explore the knowledge graph by traversing from a named entity. "
            "Returns neighboring nodes and edges up to the specified depth."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name of the entity to start exploration from",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to traverse from the entity (default: 1)",
                    "default": 1,
                },
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "simulation_data",
        "description": (
            "Query simulation statistics and activity data. Supports multiple query types: "
            "'summary' (overall stats), 'top_posts' (most engaged posts), "
            "'agent_activity' (per-agent action counts), 'timeline' (actions per round), "
            "'action_counts' (counts by action type)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["summary", "top_posts", "agent_activity", "timeline", "action_counts"],
                    "description": "The type of simulation data to retrieve",
                },
                "filters": {
                    "type": "object",
                    "description": "Optional filters (e.g., {platform: 'twitter', round: 2})",
                },
            },
            "required": ["query_type"],
        },
    },
    {
        "name": "interview_agent",
        "description": (
            "Interview a specific simulation agent in character. "
            "The agent responds from their persona and experience in the simulation."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "The numeric ID of the agent to interview",
                },
                "question": {
                    "type": "string",
                    "description": "The question to ask the agent",
                },
            },
            "required": ["agent_id", "question"],
        },
    },
    {
        "name": "agent_actions",
        "description": (
            "Retrieve all actions taken by a specific agent during the simulation. "
            "Optionally filter by action type."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_id": {
                    "type": "integer",
                    "description": "The numeric ID of the agent",
                },
                "action_type": {
                    "type": "string",
                    "description": "Optional action type filter (e.g., 'CREATE_POST', 'LIKE_POST')",
                },
            },
            "required": ["agent_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_graph_search(
    ctx: ToolContext,
    query: str,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """Semantic search over the knowledge graph via ChromaDB."""
    if ctx.chroma_collection is None:
        logger.warning("graph_search: chroma_collection is unavailable")
        return []

    try:
        response = ctx.chroma_collection.query(
            query_texts=[query],
            n_results=n_results,
        )
    except Exception as exc:
        logger.error("graph_search query failed: %s", exc)
        return []

    results: list[dict[str, Any]] = []
    ids = response.get("ids", [[]])[0]
    documents = response.get("documents", [[]])[0]
    metadatas = response.get("metadatas", [[]])[0]
    distances = response.get("distances", [[]])[0]

    for i, doc_id in enumerate(ids):
        results.append(
            {
                "id": doc_id,
                "text": documents[i] if i < len(documents) else "",
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else None,
            }
        )

    return results


def tool_graph_explore(
    ctx: ToolContext,
    entity_name: str,
    depth: int = 1,
) -> dict[str, Any] | str:
    """BFS exploration of the knowledge graph from a named entity."""
    graph = ctx.graph

    if entity_name not in graph:
        return f"Entity '{entity_name}' not found in the knowledge graph."

    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque([(entity_name, 0)])
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    while queue:
        current, current_depth = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        node_data = dict(graph.nodes[current])
        nodes.append({"name": current, **node_data})

        if current_depth >= depth:
            continue

        # Traverse successors (outgoing edges)
        for successor in graph.successors(current):
            edge_data = dict(graph.edges[current, successor])
            edges.append({"source": current, "target": successor, **edge_data})
            if successor not in visited:
                queue.append((successor, current_depth + 1))

        # Traverse predecessors (incoming edges)
        for predecessor in graph.predecessors(current):
            edge_data = dict(graph.edges[predecessor, current])
            edges.append({"source": predecessor, "target": current, **edge_data})
            if predecessor not in visited:
                queue.append((predecessor, current_depth + 1))

    return {"entity": entity_name, "nodes": nodes, "edges": edges}


def tool_simulation_data(
    ctx: ToolContext,
    query_type: str,
    filters: dict[str, Any] | None = None,
) -> Any:
    """Query simulation statistics from the database."""
    sim_id = ctx.simulation_id
    filters = filters or {}

    with get_db(ctx.db_path) as conn:
        if query_type == "summary":
            total_row = conn.execute(
                "SELECT COUNT(*) as cnt FROM simulation_actions WHERE simulation_id = ?",
                (sim_id,),
            ).fetchone()
            total_actions = total_row["cnt"] if total_row else 0

            action_rows = conn.execute(
                "SELECT action_type, COUNT(*) as cnt FROM simulation_actions "
                "WHERE simulation_id = ? GROUP BY action_type",
                (sim_id,),
            ).fetchall()
            action_counts = {row["action_type"]: row["cnt"] for row in action_rows}

            agent_row = conn.execute(
                "SELECT COUNT(DISTINCT agent_id) as cnt FROM simulation_actions WHERE simulation_id = ?",
                (sim_id,),
            ).fetchone()
            agent_count = agent_row["cnt"] if agent_row else 0

            round_row = conn.execute(
                "SELECT MAX(round) as max_round FROM simulation_actions WHERE simulation_id = ?",
                (sim_id,),
            ).fetchone()
            total_rounds = round_row["max_round"] if round_row else 0

            platform_rows = conn.execute(
                "SELECT DISTINCT platform FROM simulation_actions WHERE simulation_id = ?",
                (sim_id,),
            ).fetchall()
            platforms = [row["platform"] for row in platform_rows]

            return {
                "total_actions": total_actions,
                "action_counts": action_counts,
                "agent_count": agent_count,
                "total_rounds": total_rounds,
                "platforms": platforms,
            }

        elif query_type == "action_counts":
            rows = conn.execute(
                "SELECT action_type, COUNT(*) as cnt FROM simulation_actions "
                "WHERE simulation_id = ? GROUP BY action_type",
                (sim_id,),
            ).fetchall()
            return {row["action_type"]: row["cnt"] for row in rows}

        elif query_type == "agent_activity":
            rows = conn.execute(
                "SELECT agent_id, agent_name, COUNT(*) as action_count "
                "FROM simulation_actions WHERE simulation_id = ? "
                "GROUP BY agent_id, agent_name ORDER BY action_count DESC",
                (sim_id,),
            ).fetchall()
            return [
                {
                    "agent_id": row["agent_id"],
                    "agent_name": row["agent_name"],
                    "action_count": row["action_count"],
                }
                for row in rows
            ]

        elif query_type == "timeline":
            rows = conn.execute(
                "SELECT round, COUNT(*) as action_count FROM simulation_actions "
                "WHERE simulation_id = ? GROUP BY round ORDER BY round ASC",
                (sim_id,),
            ).fetchall()
            return [
                {"round": row["round"], "action_count": row["action_count"]}
                for row in rows
            ]

        elif query_type == "top_posts":
            # Find CREATE_POST actions, then count likes and comments referencing each post
            post_rows = conn.execute(
                "SELECT id, agent_id, agent_name, content, round, timestamp "
                "FROM simulation_actions "
                "WHERE simulation_id = ? AND action_type = 'CREATE_POST'",
                (sim_id,),
            ).fetchall()

            # Fetch all engagement actions once (not per-post)
            like_rows = conn.execute(
                "SELECT content FROM simulation_actions "
                "WHERE simulation_id = ? AND action_type = 'LIKE_POST'",
                (sim_id,),
            ).fetchall()
            comment_rows = conn.execute(
                "SELECT content FROM simulation_actions "
                "WHERE simulation_id = ? AND action_type = 'CREATE_COMMENT'",
                (sim_id,),
            ).fetchall()

            # Build engagement counts indexed by post_id string
            like_counts: dict[str, int] = {}
            for lr in like_rows:
                try:
                    data = json.loads(lr["content"] or "{}")
                    pid = str(data.get("post_id", ""))
                    if pid:
                        like_counts[pid] = like_counts.get(pid, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

            comment_counts: dict[str, int] = {}
            for cr in comment_rows:
                try:
                    data = json.loads(cr["content"] or "{}")
                    pid = str(data.get("post_id", ""))
                    if pid:
                        comment_counts[pid] = comment_counts.get(pid, 0) + 1
                except (json.JSONDecodeError, TypeError):
                    pass

            results = []
            for post_row in post_rows:
                post_id_str = str(post_row["id"])
                likes = like_counts.get(post_id_str, 0)
                comments = comment_counts.get(post_id_str, 0)

                try:
                    post_content = json.loads(post_row["content"] or "{}")
                    text = post_content.get("content", "")
                except (json.JSONDecodeError, TypeError):
                    text = post_row["content"] or ""

                results.append(
                    {
                        "post_id": post_row["id"],
                        "agent_id": post_row["agent_id"],
                        "agent_name": post_row["agent_name"],
                        "content": text,
                        "round": post_row["round"],
                        "timestamp": post_row["timestamp"],
                        "likes": likes,
                        "comments": comments,
                        "engagement": likes + comments,
                    }
                )

            results.sort(key=lambda x: x["engagement"], reverse=True)
            return results

        else:
            return {"error": f"Unknown query_type: {query_type!r}"}


def tool_agent_actions(
    ctx: ToolContext,
    agent_id: int,
    action_type: str | None = None,
) -> list[dict[str, Any]]:
    """Retrieve all actions taken by a specific agent during the simulation."""
    sim_id = ctx.simulation_id

    with get_db(ctx.db_path) as conn:
        if action_type:
            rows = conn.execute(
                "SELECT * FROM simulation_actions "
                "WHERE simulation_id = ? AND agent_id = ? AND action_type = ? "
                "ORDER BY round ASC, timestamp ASC",
                (sim_id, agent_id, action_type),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM simulation_actions "
                "WHERE simulation_id = ? AND agent_id = ? "
                "ORDER BY round ASC, timestamp ASC",
                (sim_id, agent_id),
            ).fetchall()

        return [dict(row) for row in rows]


def tool_interview_agent(
    ctx: ToolContext,
    agent_id: int,
    question: str,
) -> str:
    """Interview a specific simulation agent in character."""
    # Find the agent profile
    profile = None
    for p in ctx.profiles:
        if p.agent_id == agent_id:
            profile = p
            break

    if profile is None:
        return f"Agent with id {agent_id} not found."

    # Load domain config and agent_system prompt
    try:
        domain = load_domain("_default", ctx.domains_dir)
        system_template_text = read_prompt(domain, "agent_system")
    except Exception as exc:
        logger.warning("Could not load agent_system prompt: %s — using fallback", exc)
        system_template_text = "You are {{ agent_name }}. {{ persona }}"

    # Render template with agent profile variables
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

    # Inject agent's own actions from the simulation as context
    actions = tool_agent_actions(ctx, agent_id=agent_id)
    if actions:
        action_lines = []
        for a in actions:
            action_lines.append(f"- Round {a.get('round', '?')}: {a.get('action_type', '?')} — {a.get('content', '')}")
        actions_text = "\n".join(action_lines)
        system_prompt += (
            f"\n\nHere is what you did during the simulation:\n{actions_text}"
        )

    messages = [{"role": "user", "content": question}]

    try:
        response = ctx.client.complete(messages=messages, system=system_prompt)
        return response.text
    except Exception as exc:
        logger.error("interview_agent LLM call failed: %s", exc)
        return f"Error interviewing agent {agent_id}: {exc}"


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def execute_tool(
    ctx: ToolContext,
    tool_name: str,
    tool_input: dict[str, Any],
) -> Any:
    """Dispatch a tool call to the appropriate implementation."""
    if tool_name == "graph_search":
        return tool_graph_search(ctx, **tool_input)
    elif tool_name == "graph_explore":
        return tool_graph_explore(ctx, **tool_input)
    elif tool_name == "simulation_data":
        return tool_simulation_data(ctx, **tool_input)
    elif tool_name == "agent_actions":
        return tool_agent_actions(ctx, **tool_input)
    elif tool_name == "interview_agent":
        return tool_interview_agent(ctx, **tool_input)
    else:
        raise ValueError(f"Unknown tool: {tool_name!r}")
