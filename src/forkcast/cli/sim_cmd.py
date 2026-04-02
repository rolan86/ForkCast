"""CLI commands for simulation management."""

import json
import secrets
from datetime import datetime, timezone
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.db.queries import get_project_domain
from forkcast.domains.loader import load_domain
from forkcast.llm.factory import create_llm_client
from forkcast.simulation.prepare import prepare_simulation

sim_app = typer.Typer(help="Manage simulations", no_args_is_help=True)


@sim_app.command("create")
def sim_create(
    project_id: str,
    engine: Annotated[str | None, typer.Option(help="Simulation engine (default: from domain manifest)")] = None,
    platforms: Annotated[str, typer.Option(help="Comma-separated platforms")] = "twitter,reddit",
):
    """Create a new simulation for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    if project is None:
        typer.echo(f"Error: Project not found: {project_id}", err=True)
        raise typer.Exit(code=1)

    # Resolve engine from domain manifest if not explicitly provided
    if engine is None:
        try:
            domain_name = get_project_domain(settings.db_path, project_id)
            domain = load_domain(domain_name, settings.domains_dir)
            engine = domain.sim_engine or "oasis"
        except Exception:
            engine = "oasis"

    # Find latest graph
    with get_db(settings.db_path) as conn:
        graph = conn.execute(
            "SELECT id FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    graph_id = graph["id"] if graph else None
    platform_list = [p.strip() for p in platforms.split(",")]
    sim_id = f"sim_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?)",
            (sim_id, project_id, graph_id, engine, json.dumps(platform_list), now),
        )

    typer.echo(f"Simulation created: {sim_id}")
    typer.echo(f"  Project:   {project_id}")
    typer.echo(f"  Engine:    {engine}")
    typer.echo(f"  Platforms: {', '.join(platform_list)}")
    if graph_id:
        typer.echo(f"  Graph:     {graph_id}")


@sim_app.command("prepare")
def sim_prepare(
    simulation_id: str,
    provider: Annotated[str | None, typer.Option("--provider", help="LLM provider (claude or ollama)")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override default model")] = None,
):
    """Prepare a simulation (generate profiles + config)."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        typer.echo(f"Error: Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Preparing simulation {simulation_id}...")
    client = create_llm_client(
        provider=provider or settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=model or settings.ollama_model,
    )
    if (provider or settings.llm_provider) == "ollama":
        typer.echo(
            f"⚠ Using local model ({model or settings.ollama_model} via Ollama). "
            "Quality may vary. Use --provider claude for production results.",
            err=True,
        )

    def on_progress(stage: str, **kwargs):
        current = kwargs.get("current", "")
        total = kwargs.get("total", "")
        if current and total:
            typer.echo(f"  [{stage}] {current}/{total}")
        else:
            typer.echo(f"  [{stage}]")

    try:
        result = prepare_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            prep_model=model or settings.ollama_model if (provider or settings.llm_provider) == "ollama" else model,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nSimulation prepared!")
    typer.echo(f"  Profiles: {result.profiles_count}")
    typer.echo(f"  Config:   {'generated' if result.config_generated else 'failed'}")
    typer.echo(f"  Tokens:   {result.tokens_used.get('input', 0)} in / {result.tokens_used.get('output', 0)} out")


@sim_app.command("list")
def sim_list():
    """List all simulations."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, project_id, status, engine_type, platforms, created_at "
            "FROM simulations ORDER BY created_at DESC"
        ).fetchall()

    if not rows:
        typer.echo("No simulations found.")
        return

    typer.echo(f"{'ID':<20} {'Project':<20} {'Status':<12} {'Engine':<10} {'Created'}")
    typer.echo("-" * 90)
    for row in rows:
        typer.echo(
            f"{row['id']:<20} {row['project_id']:<20} {row['status']:<12} "
            f"{row['engine_type']:<10} {row['created_at']}"
        )


@sim_app.command("show")
def sim_show(simulation_id: str):
    """Show simulation details."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        typer.echo(f"Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    platforms = json.loads(sim["platforms"]) if sim["platforms"] else []
    typer.echo(f"ID:        {sim['id']}")
    typer.echo(f"Project:   {sim['project_id']}")
    typer.echo(f"Graph:     {sim['graph_id'] or 'none'}")
    typer.echo(f"Status:    {sim['status']}")
    typer.echo(f"Engine:    {sim['engine_type']}")
    typer.echo(f"Platforms: {', '.join(platforms)}")
    typer.echo(f"Created:   {sim['created_at']}")
    if sim["config_json"]:
        config = json.loads(sim["config_json"])
        typer.echo(f"\nConfig:")
        typer.echo(f"  Duration:  {config.get('total_hours', '?')}h")
        typer.echo(f"  Round:     {config.get('minutes_per_round', '?')}min")
        typer.echo(f"  Topics:    {', '.join(config.get('hot_topics', []))}")


@sim_app.command("start")
def sim_start(
    simulation_id: str,
    max_rounds: Annotated[int | None, typer.Option(help="Maximum rounds to run")] = None,
    provider: Annotated[str | None, typer.Option("--provider", help="LLM provider (claude or ollama)")] = None,
    model: Annotated[str | None, typer.Option("--model", help="Override default model")] = None,
    decision_model: Annotated[str | None, typer.Option("--decision-model", help="Model for low-creativity decision actions")] = None,
    creative_model: Annotated[str | None, typer.Option("--creative-model", help="Model for high-creativity content actions")] = None,
    compress_feed: Annotated[bool | None, typer.Option("--compress-feed/--no-compress-feed", help="Compress feed context to reduce tokens")] = None,
):
    """Start running a prepared simulation."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status, engine_type, config_json FROM simulations WHERE id = ?",
            (simulation_id,),
        ).fetchone()

    if sim is None:
        typer.echo(f"Error: Simulation not found: {simulation_id}", err=True)
        raise typer.Exit(code=1)

    if sim["status"] != "prepared":
        typer.echo(f"Error: Simulation must be 'prepared' to start (current: {sim['status']})", err=True)
        raise typer.Exit(code=1)

    # When using Ollama, default decision/creative models to the Ollama model
    effective_provider = provider or settings.llm_provider
    if effective_provider == "ollama":
        ollama_model_name = model or settings.ollama_model
        if decision_model is None:
            decision_model = ollama_model_name
        if creative_model is None:
            creative_model = ollama_model_name

    # Merge optimization CLI flags into config_json before running
    config_overrides = {}
    if decision_model is not None:
        config_overrides["decision_model"] = decision_model
    if creative_model is not None:
        config_overrides["creative_model"] = creative_model
    if compress_feed is not None:
        config_overrides["compress_feed"] = compress_feed

    if config_overrides:
        existing_config = json.loads(sim["config_json"]) if sim["config_json"] else {}
        existing_config.update(config_overrides)
        with get_db(settings.db_path) as conn:
            conn.execute(
                "UPDATE simulations SET config_json = ?, updated_at = datetime('now') WHERE id = ?",
                (json.dumps(existing_config), simulation_id),
            )

    typer.echo(f"Starting simulation {simulation_id} (engine: {sim['engine_type']})...")
    client = create_llm_client(
        provider=provider or settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=model or settings.ollama_model,
    )
    if (provider or settings.llm_provider) == "ollama":
        typer.echo(
            f"⚠ Using local model ({model or settings.ollama_model} via Ollama). "
            "Quality may vary. Use --provider claude for production results.",
            err=True,
        )

    def on_progress(stage: str, **kwargs):
        if stage == "round":
            typer.echo(f"  [round] {kwargs.get('current', '?')}/{kwargs.get('total', '?')}")
        elif stage == "action":
            agent = kwargs.get("agent_name", "?")
            atype = kwargs.get("action_type", "?")
            typer.echo(f"  [action] {agent}: {atype}")
        elif stage not in ("loading", "running"):
            typer.echo(f"  [{stage}]")

    try:
        from forkcast.simulation.runner import run_simulation
        result = run_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            max_rounds=max_rounds,
        )
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"\nSimulation complete!")
    typer.echo(f"  Actions: {result.actions_count}")
    typer.echo(f"  Rounds:  {result.total_rounds}")
    typer.echo(f"  Output:  {result.actions_path}")
    if result.tokens_used:
        typer.echo(f"  Tokens:  {result.tokens_used.get('input', 0)} in / {result.tokens_used.get('output', 0)} out")
