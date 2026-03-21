"""Report generation pipeline — tool-use loop with progress events and error handling."""

import json
import logging
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import networkx as nx

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.graph.graph_store import load_graph
from forkcast.llm.client import ClaudeClient
from forkcast.report.models import ReportResult, ToolContext
from forkcast.report.tools import REPORT_TOOLS, execute_tool
from forkcast.simulation.models import AgentProfile

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOOL_ROUNDS = 10


def _emit(on_progress: Callable | None, **kwargs: Any) -> None:
    """Emit a progress event if a callback is provided."""
    if on_progress is not None:
        on_progress(**kwargs)


def _load_profiles(profiles_path: Path) -> list[AgentProfile]:
    """Load agent profiles from agents.json."""
    if not profiles_path.exists():
        logger.warning("Profiles file not found: %s", profiles_path)
        return []
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


def _load_graph_optional(graph_path: Path) -> nx.DiGraph:
    """Load graph from disk, returning empty graph if missing."""
    if graph_path.exists():
        try:
            return load_graph(graph_path)
        except Exception as exc:
            logger.warning("Could not load graph from %s: %s", graph_path, exc)
    return nx.DiGraph()


def _load_chroma_optional(chroma_dir: Path) -> Any:
    """Load ChromaDB collection if available, else return None."""
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
        logger.warning("Could not load ChromaDB from %s: %s", chroma_dir, exc)
        return None


def _build_system_prompt(domain_guidelines: str, simulation_summary: dict[str, Any]) -> str:
    """Combine report guidelines with simulation summary context."""
    summary_text = json.dumps(simulation_summary, indent=2)
    return (
        f"{domain_guidelines}\n\n"
        f"## Simulation Summary\n\n```json\n{summary_text}\n```\n"
    )


def _get_simulation_summary(db_path: Path, simulation_id: str) -> dict[str, Any]:
    """Fetch a brief simulation summary from the database."""
    with get_db(db_path) as conn:
        sim_row = conn.execute(
            "SELECT s.*, p.requirement, p.domain FROM simulations s "
            "JOIN projects p ON s.project_id = p.id "
            "WHERE s.id = ?",
            (simulation_id,),
        ).fetchone()

        total_row = conn.execute(
            "SELECT COUNT(*) as cnt FROM simulation_actions WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()

        agent_row = conn.execute(
            "SELECT COUNT(DISTINCT agent_id) as cnt FROM simulation_actions WHERE simulation_id = ?",
            (simulation_id,),
        ).fetchone()

    if sim_row is None:
        return {"simulation_id": simulation_id}

    return {
        "simulation_id": simulation_id,
        "requirement": sim_row["requirement"],
        "domain": sim_row["domain"],
        "platforms": json.loads(sim_row["platforms"] or "[]"),
        "total_actions": total_row["cnt"] if total_row else 0,
        "agent_count": agent_row["cnt"] if agent_row else 0,
    }


def _get_project_id(db_path: Path, simulation_id: str) -> str:
    """Get project_id for a given simulation."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT project_id FROM simulations WHERE id = ?",
            (simulation_id,),
        ).fetchone()
    if row is None:
        raise ValueError(f"Simulation not found: {simulation_id!r}")
    return row["project_id"]


def _create_report_record(db_path: Path, simulation_id: str, report_id: str | None = None) -> str:
    """Insert a new report row with 'generating' status, return its id."""
    if report_id is None:
        report_id = f"report_{secrets.token_hex(8)}"
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO reports (id, simulation_id, status, created_at) VALUES (?, ?, 'generating', ?)",
            (report_id, simulation_id, now),
        )
    return report_id


def _update_report_status(
    db_path: Path,
    report_id: str,
    status: str,
    content_markdown: str | None = None,
    tool_history: list | None = None,
) -> None:
    """Update report status (and optionally content) in the database."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db(db_path) as conn:
        if status == "completed" and content_markdown is not None:
            conn.execute(
                "UPDATE reports SET status = ?, content_markdown = ?, "
                "tool_history_json = ?, completed_at = ? WHERE id = ?",
                (
                    status,
                    content_markdown,
                    json.dumps(tool_history or []),
                    now,
                    report_id,
                ),
            )
        else:
            conn.execute(
                "UPDATE reports SET status = ? WHERE id = ?",
                (status, report_id),
            )


def _log_token_usage(
    db_path: Path,
    project_id: str,
    stage: str,
    input_tokens: int,
    output_tokens: int,
    model: str = "",
) -> None:
    """Persist token usage for billing/monitoring."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO token_usage (project_id, stage, input_tokens, output_tokens, model) "
            "VALUES (?, ?, ?, ?, ?)",
            (project_id, stage, input_tokens, output_tokens, model),
        )


def generate_report(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    client: ClaudeClient,
    domains_dir: Path,
    max_tool_rounds: int = DEFAULT_MAX_TOOL_ROUNDS,
    on_progress: Callable | None = None,
    report_id: str | None = None,
) -> ReportResult:
    """
    Generate a prediction report from simulation results via a tool-use loop.

    Steps:
    1. Load simulation context (profiles, graph, ChromaDB)
    2. Create a 'generating' report record in the DB
    3. Build system prompt from report_guidelines + simulation summary
    4. Run tool-use loop (up to max_tool_rounds rounds)
    5. Persist final report, log token usage
    6. On exception, mark report as 'failed' and re-raise
    """
    _emit(on_progress, stage="loading", message="Loading simulation context...")

    # --- Load context ---
    project_id = _get_project_id(db_path, simulation_id)
    sim_dir = data_dir / simulation_id
    project_dir = data_dir / project_id
    profiles_path = sim_dir / "profiles" / "agents.json"
    graph_path = project_dir / "graph.json"
    chroma_dir = project_dir / "chroma"

    profiles = _load_profiles(profiles_path)
    graph = _load_graph_optional(graph_path)
    chroma_collection = _load_chroma_optional(chroma_dir)

    # --- Load domain guidelines ---
    try:
        domain = load_domain("_default", domains_dir)
        guidelines = read_prompt(domain, "report_guidelines")
    except Exception as exc:
        logger.warning("Could not load report_guidelines: %s — using empty", exc)
        guidelines = "You are a report analyst. Generate a comprehensive prediction report."

    # --- Create DB record ---
    report_id = _create_report_record(db_path, simulation_id, report_id=report_id)

    # Build tool context
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

    # Build system prompt
    sim_summary = _get_simulation_summary(db_path, simulation_id)
    system_prompt = _build_system_prompt(guidelines, sim_summary)

    # Initial user message
    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Please analyze the simulation data and generate a comprehensive prediction report. "
                "Use the available tools to gather evidence before writing your conclusions."
            ),
        }
    ]

    tool_rounds = 0
    total_input_tokens = 0
    total_output_tokens = 0
    tool_history: list[dict[str, Any]] = []
    final_text = ""

    try:
        _emit(on_progress, stage="thinking", message="Starting report generation...")

        for _round in range(max_tool_rounds + 1):
            response = client.tool_use(
                messages=messages,
                tools=REPORT_TOOLS,
                system=system_prompt,
            )

            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens

            # Append assistant message — use raw content blocks if available
            raw_content = response.raw.content if response.raw is not None else []
            messages.append({"role": "assistant", "content": raw_content if raw_content else response.text})

            if not response.tool_calls:
                # No tool calls — this is the final report
                final_text = response.text
                break

            # Process tool calls
            tool_rounds += 1
            _emit(
                on_progress,
                stage="tool_use",
                message=f"Round {tool_rounds}: executing {len(response.tool_calls)} tool(s)...",
                tool_round=tool_rounds,
            )

            tool_results: list[dict[str, Any]] = []
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_input = tc["input"]
                tool_id = tc["id"]

                logger.debug("Executing tool %r with input %r", tool_name, tool_input)
                try:
                    result = execute_tool(ctx, tool_name, tool_input)
                except Exception as exc:
                    logger.error("Tool %r failed: %s", tool_name, exc)
                    result = {"error": str(exc)}

                tool_history.append(
                    {"round": tool_rounds, "tool": tool_name, "input": tool_input, "result": result}
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(result, default=str),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        else:
            # Exceeded max_tool_rounds — force generation without tools
            logger.warning(
                "Max tool rounds (%d) reached for simulation %s — forcing final generation",
                max_tool_rounds,
                simulation_id,
            )
            _emit(on_progress, stage="forcing", message="Max tool rounds reached, generating report...")
            response = client.complete(messages=messages, system=system_prompt)
            total_input_tokens += response.input_tokens
            total_output_tokens += response.output_tokens
            final_text = response.text

        # Persist completed report
        _update_report_status(
            db_path,
            report_id,
            status="completed",
            content_markdown=final_text,
            tool_history=tool_history,
        )

        _log_token_usage(
            db_path,
            project_id,
            stage="report",
            input_tokens=total_input_tokens,
            output_tokens=total_output_tokens,
        )

        _emit(
            on_progress,
            stage="complete",
            message="Report generation complete.",
            report_id=report_id,
        )

        return ReportResult(
            report_id=report_id,
            simulation_id=simulation_id,
            content_markdown=final_text,
            tool_rounds=tool_rounds,
            tokens_used={
                "input": total_input_tokens,
                "output": total_output_tokens,
            },
        )

    except Exception:
        # Mark report as failed and re-raise
        try:
            _update_report_status(db_path, report_id, status="failed")
        except Exception as db_exc:
            logger.error("Could not mark report as failed: %s", db_exc)
        raise
