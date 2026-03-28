"""Orchestrate simulation preparation: profiles + config generation."""

import json
import logging
import shutil
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.llm.client import LLMClient
from forkcast.simulation.config_generator import generate_config
from forkcast.simulation.models import AgentProfile, PrepareResult
from forkcast.simulation.profile_generator import generate_profiles

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None] | None


def find_reusable_profiles(
    db_path: Path,
    data_dir: Path,
    project_id: str,
    graph_id: str | None,
    domain: str,
) -> dict | None:
    """Find the most recent simulation with reusable profiles.

    Returns {"simulation_id": str, "count": int, "path": Path} or None.
    """
    if graph_id is None:
        return None

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT s.id FROM simulations s
               JOIN projects p ON s.project_id = p.id
               WHERE s.project_id = ? AND s.graph_id IS NOT NULL AND s.graph_id = ?
               AND p.domain = ?
               ORDER BY s.created_at DESC LIMIT 10""",
            (project_id, graph_id, domain),
        ).fetchall()

    for r in rows:
        profiles_path = data_dir / r["id"] / "profiles" / "agents.json"
        if profiles_path.exists():
            try:
                data = json.loads(profiles_path.read_text(encoding="utf-8"))
                if data:
                    return {
                        "simulation_id": r["id"],
                        "count": len(data),
                        "path": profiles_path,
                    }
            except (json.JSONDecodeError, KeyError):
                continue
    return None


def prepare_simulation(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    client: LLMClient,
    domains_dir: Path,
    on_progress: ProgressCallback = None,
    force_regenerate: bool = False,
    prep_model: str | None = None,
) -> PrepareResult:
    """Run the full prepare pipeline: load graph -> generate profiles -> generate config."""

    def _progress(stage: str, **kwargs: Any) -> None:
        if on_progress:
            on_progress(stage=stage, **kwargs)

    # 1. Load simulation and related data
    with get_db(db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        raise ValueError(f"Simulation not found: {simulation_id}")

    project_id = sim["project_id"]
    graph_id = sim["graph_id"]

    # Use prep_model from DB if not passed explicitly
    if prep_model is None:
        prep_model = sim["prep_model"] if sim["prep_model"] else None

    with get_db(db_path) as conn:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        graph_row = conn.execute(
            "SELECT * FROM graphs WHERE id = ?", (graph_id,)
        ).fetchone()

    if project is None:
        raise ValueError(f"Project not found: {project_id}")
    if graph_row is None:
        raise ValueError(f"Graph not found: {graph_id}")

    # 2. Load graph data
    _progress("loading_graph")
    graph_path = Path(graph_row["file_path"])
    if not graph_path.exists():
        # Try relative to data_dir
        graph_path = data_dir / project_id / "graph.json"
    graph_data = json.loads(graph_path.read_text(encoding="utf-8"))

    # Extract entities from graph nodes
    entities = []
    for node in graph_data.get("nodes", []):
        entities.append({
            "name": node.get("id", node.get("name", "")),
            "type": node.get("type", "Unknown"),
            "description": node.get("description", ""),
        })

    # 3. Load domain and prompt templates
    domain = load_domain(project["domain"], domains_dir)
    persona_template = read_prompt(domain, "persona")
    config_template = read_prompt(domain, "config_generation")

    # 4. Generate profiles (with reuse and incremental saving for recovery)
    sim_dir = data_dir / simulation_id
    profiles_dir = sim_dir / "profiles"

    # Check for reusable profiles (unless force_regenerate)
    reuse_info = None
    if not force_regenerate:
        reuse_info = find_reusable_profiles(
            db_path=db_path,
            data_dir=data_dir,
            project_id=project_id,
            graph_id=graph_id,
            domain=project["domain"],
        )

    if reuse_info is not None and reuse_info["simulation_id"] != simulation_id:
        # Copy profiles from previous simulation
        profiles_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reuse_info["path"], profiles_dir / "agents.json")
        _progress("generating_profiles", current=reuse_info["count"], total=reuse_info["count"], reused=True)
        # Load reused profiles as AgentProfile objects
        reused_data = json.loads((profiles_dir / "agents.json").read_text(encoding="utf-8"))
        profiles = [AgentProfile(**p) for p in reused_data]
        profile_tokens = {"input": 0, "output": 0}
    else:
        _progress("generating_profiles", total=len(entities))
        profiles, profile_tokens = generate_profiles(
            client=client,
            entities=entities,
            graph_data=graph_data,
            requirement=project["requirement"],
            persona_template=persona_template,
            profiles_dir=profiles_dir,
            on_progress=lambda current, total: _progress(
                "generating_profiles", current=current, total=total
            ),
            model=prep_model,
        )
    profiles_path = profiles_dir / "agents.json"

    # Read user timing overrides from DB row (may be None)
    user_total_hours = sim["total_hours"] if sim["total_hours"] else None
    user_minutes_per_round = sim["minutes_per_round"] if sim["minutes_per_round"] else None

    # 5. Generate config
    _progress("generating_config")
    config, config_tokens = generate_config(
        client=client,
        profiles=profiles,
        requirement=project["requirement"],
        config_template=config_template,
        model=prep_model,
        user_total_hours=user_total_hours,
        user_minutes_per_round=user_minutes_per_round,
    )

    # 6. Persist config and update simulation status
    config_json = json.dumps(config.to_dict())
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'prepared', config_json = ?, "
            "updated_at = datetime('now') WHERE id = ?",
            (config_json, simulation_id),
        )

    # 7. Log token usage
    total_input = profile_tokens["input"] + config_tokens["input"]
    total_output = profile_tokens["output"] + config_tokens["output"]
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO token_usage (project_id, stage, model, input_tokens, output_tokens, created_at) "
            "VALUES (?, 'simulation_prep', ?, ?, ?, datetime('now'))",
            (project_id, str(client.default_model), total_input, total_output),
        )

    _progress("complete")

    return PrepareResult(
        simulation_id=simulation_id,
        profiles_count=len(profiles),
        profiles_path=str(profiles_path),
        config_generated=True,
        tokens_used={"input": total_input, "output": total_output},
    )
