"""Simulation management API routes with SSE streaming."""

import asyncio
import json
import logging
import math
import secrets
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.prepare import prepare_simulation
from forkcast.simulation.runner import run_simulation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

_VALID_AGENT_MODES = {"llm", "native"}

# Per-simulation progress queues. Created on POST /prepare, consumed by GET /prepare/stream.
_prepare_queues: dict[str, asyncio.Queue] = {}


class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str | None = None
    platforms: list[str] | None = None
    agent_mode: str | None = None  # "llm" or "native"


class UpdateSettingsRequest(BaseModel):
    engine_type: str | None = None
    platforms: list[str] | None = None
    prep_model: str | None = None
    run_model: str | None = None
    agent_mode: str | None = None  # "llm" or "native"


@router.post("")
async def create_simulation(req: CreateSimulationRequest):
    """Create a new simulation for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, domain, status FROM projects WHERE id = ?", (req.project_id,)
        ).fetchone()

    if project is None:
        return error(f"Project not found: {req.project_id}", status_code=404)

    # Load domain defaults for engine/platforms when not explicitly provided
    domain_name = project["domain"] if project["domain"] else "_default"
    try:
        domain = load_domain(domain_name, settings.domains_dir)
        default_engine = domain.sim_engine
        default_platforms = domain.platforms
    except Exception:
        default_engine = "claude"
        default_platforms = ["twitter", "reddit"]

    engine_type = req.engine_type if req.engine_type is not None else default_engine
    platforms = req.platforms if req.platforms is not None else default_platforms

    agent_mode = req.agent_mode or "llm"
    if agent_mode not in _VALID_AGENT_MODES:
        return error(f"Invalid agent_mode: {agent_mode}. Must be one of: {_VALID_AGENT_MODES}", status_code=400)

    # Find the latest graph for this project
    with get_db(settings.db_path) as conn:
        graph = conn.execute(
            "SELECT id FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (req.project_id,),
        ).fetchone()

    graph_id = graph["id"] if graph else None

    sim_id = f"sim_{secrets.token_hex(6)}"
    now = datetime.now(timezone.utc).isoformat()

    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, agent_mode, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?, ?)",
            (sim_id, req.project_id, graph_id, engine_type, json.dumps(platforms), agent_mode, now),
        )

    return success(
        {
            "id": sim_id,
            "project_id": req.project_id,
            "graph_id": graph_id,
            "status": "created",
            "engine_type": engine_type,
            "platforms": platforms,
            "agent_mode": agent_mode,
            "created_at": now,
        },
        status_code=201,
    )


@router.get("")
async def list_simulations():
    """List all simulations with computed action counts and round info."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT s.id, s.project_id, s.graph_id, s.status, s.engine_type, "
            "s.platforms, s.agent_mode, s.config_json, s.created_at, s.updated_at, "
            "COUNT(a.id) AS actions_count, MAX(a.round) AS rounds_completed "
            "FROM simulations s "
            "LEFT JOIN simulation_actions a ON a.simulation_id = s.id "
            "GROUP BY s.id "
            "ORDER BY s.created_at DESC"
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["platforms"] = json.loads(d["platforms"]) if d["platforms"] else []
        # Compute total_rounds from config's total_hours / minutes_per_round
        total_rounds = None
        if d.get("config_json"):
            try:
                config = json.loads(d["config_json"])
                total_hours = config.get("total_hours")
                minutes_per_round = config.get("minutes_per_round")
                if total_hours and minutes_per_round:
                    total_rounds = math.ceil(total_hours * 60 / minutes_per_round)
            except (json.JSONDecodeError, TypeError):
                pass
        d["total_rounds"] = total_rounds
        d["actions_count"] = d["actions_count"] or 0
        d["rounds_completed"] = d["rounds_completed"] or 0
        d.pop("config_json", None)
        results.append(d)

    return success(results)


@router.get("/{simulation_id}")
async def get_simulation(simulation_id: str):
    """Get simulation details."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    d = dict(sim)
    d["platforms"] = json.loads(d["platforms"]) if d["platforms"] else []
    if d.get("config_json"):
        d["config"] = json.loads(d["config_json"])
    d.pop("config_json", None)
    return success(d)


@router.patch("/{simulation_id}/settings")
async def update_settings(simulation_id: str, req: UpdateSettingsRequest):
    """Update simulation settings (engine, platforms, models). Only allowed before completion."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        sim = conn.execute("SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)).fetchone()
    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)
    if sim["status"] == "completed":
        return error("Cannot update settings: simulation is completed", status_code=409)
    if sim["status"] == "running" and simulation_id in _run_queues:
        return error("Cannot update settings: simulation is running", status_code=409)
    if sim["status"] == "preparing" and simulation_id in _prepare_queues:
        return error("Cannot update settings: preparation is in progress", status_code=409)

    updates = []
    params = []
    if req.engine_type is not None:
        updates.append("engine_type = ?")
        params.append(req.engine_type)
    if req.platforms is not None:
        updates.append("platforms = ?")
        params.append(json.dumps(req.platforms))
    if req.prep_model is not None:
        updates.append("prep_model = ?")
        params.append(req.prep_model)
    if req.run_model is not None:
        updates.append("run_model = ?")
        params.append(req.run_model)
    if req.agent_mode is not None:
        if req.agent_mode not in _VALID_AGENT_MODES:
            return error(f"Invalid agent_mode: {req.agent_mode}. Must be one of: {_VALID_AGENT_MODES}", status_code=400)
        updates.append("agent_mode = ?")
        params.append(req.agent_mode)

    if not updates:
        return success({"updated": False})

    updates.append("updated_at = datetime('now')")
    params.append(simulation_id)
    with get_db(settings.db_path) as conn:
        conn.execute(f"UPDATE simulations SET {', '.join(updates)} WHERE id = ?", params)

    return success({"updated": True, "simulation_id": simulation_id})


class PrepareRequest(BaseModel):
    force_regenerate: bool = False


@router.post("/{simulation_id}/prepare")
async def trigger_prepare(simulation_id: str, req: PrepareRequest | None = None):
    """Trigger simulation preparation as a background task.

    Returns immediately with status 'preparing'. Monitor progress via
    GET /api/simulations/{id}/prepare/stream (SSE).

    Accepts optional JSON body with force_regenerate to skip profile reuse.
    Also allows resuming a simulation in 'preparing' status.
    """
    settings = get_settings()
    force_regen = req.force_regenerate if req else False

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status, prep_model FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    prep_model = sim["prep_model"] if sim["prep_model"] else None

    # Persist preparing status so tab navigation can detect it
    with get_db(settings.db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'preparing', updated_at = datetime('now') WHERE id = ?",
            (simulation_id,),
        )

    # Create a queue for this simulation's progress events
    queue: asyncio.Queue = asyncio.Queue()
    _prepare_queues[simulation_id] = queue
    loop = asyncio.get_running_loop()

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        # Thread-safe: put_nowait from worker thread via call_soon_threadsafe
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _run_prepare():
        return prepare_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            force_regenerate=force_regen,
            prep_model=prep_model,
        )

    async def _background_prepare():
        try:
            result = await asyncio.to_thread(_run_prepare)
            queue.put_nowait({
                "stage": "result",
                "simulation_id": result.simulation_id,
                "profiles_count": result.profiles_count,
                "config_generated": result.config_generated,
                "tokens_used": result.tokens_used,
            })
        except Exception as e:
            logger.exception(f"Simulation prepare failed for {simulation_id}")
            with get_db(settings.db_path) as conn:
                conn.execute(
                    "UPDATE simulations SET status = 'failed', updated_at = datetime('now') WHERE id = ?",
                    (simulation_id,),
                )
            queue.put_nowait({"stage": "error", "message": str(e)})
        finally:
            queue.put_nowait(None)  # Sentinel to close SSE stream

    # Fire and forget — client monitors via SSE stream
    asyncio.create_task(_background_prepare())

    return success({"status": "preparing", "simulation_id": simulation_id})


@router.get("/{simulation_id}/prepare/stream")
async def stream_prepare(simulation_id: str, request: Request):
    """SSE stream for simulation preparation progress."""
    queue = _prepare_queues.get(simulation_id)
    if queue is None:
        return error("No prepare job running for this simulation", status_code=404)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                _prepare_queues.pop(simulation_id, None)
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


# --- Run simulation endpoints ---

# Per-simulation run queues and stop events
_run_queues: dict[str, asyncio.Queue] = {}
_stop_events: dict[str, threading.Event] = {}


@router.post("/{simulation_id}/start")
async def start_simulation(simulation_id: str):
    """Start running a prepared simulation as a background task."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)
    if sim["status"] not in ("prepared", "running"):
        return error(f"Simulation must be in 'prepared' or 'running' status to start (current: {sim['status']})", status_code=400)

    queue: asyncio.Queue = asyncio.Queue()
    _run_queues[simulation_id] = queue
    stop_event = threading.Event()
    _stop_events[simulation_id] = stop_event
    loop = asyncio.get_running_loop()

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        loop.call_soon_threadsafe(queue.put_nowait, event)

    def _run():
        return run_simulation(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            simulation_id=simulation_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
            stop_event=stop_event,
        )

    async def _background_run():
        try:
            result = await asyncio.to_thread(_run)
            queue.put_nowait({
                "stage": "result",
                "simulation_id": result.simulation_id,
                "actions_count": result.actions_count,
                "total_rounds": result.total_rounds,
                "tokens_used": result.tokens_used,
            })
        except Exception as e:
            logger.exception(f"Simulation run failed for {simulation_id}")
            queue.put_nowait({"stage": "error", "message": str(e)})
        finally:
            queue.put_nowait(None)
            _stop_events.pop(simulation_id, None)

    asyncio.create_task(_background_run())

    return success({"status": "running", "simulation_id": simulation_id})


@router.post("/{simulation_id}/stop")
async def stop_simulation(simulation_id: str):
    """Stop a running simulation gracefully via stop_event."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

    stop_event = _stop_events.get(simulation_id)
    if stop_event is None:
        return error("No running simulation to stop", status_code=400)

    stop_event.set()
    return success({"status": "stopping", "simulation_id": simulation_id})


@router.get("/{simulation_id}/run/stream")
async def stream_run(simulation_id: str, request: Request):
    """SSE stream for simulation run progress and actions."""
    queue = _run_queues.get(simulation_id)
    if queue is None:
        return error("No run job active for this simulation", status_code=404)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                _run_queues.pop(simulation_id, None)
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/{simulation_id}/actions")
async def get_simulation_actions(simulation_id: str):
    """Get all recorded actions for a simulation."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()
        if sim is None:
            return error(f"Simulation not found: {simulation_id}", status_code=404)

        rows = conn.execute(
            "SELECT round, agent_id, agent_name, action_type, content, platform, timestamp "
            "FROM simulation_actions WHERE simulation_id = ? ORDER BY id",
            (simulation_id,),
        ).fetchall()

    actions = []
    for row in rows:
        d = dict(row)
        if d["content"]:
            try:
                d["action_args"] = json.loads(d["content"])
            except json.JSONDecodeError:
                d["action_args"] = {"content": d["content"]}
        else:
            d["action_args"] = {}
        d.pop("content", None)
        actions.append(d)

    return success(actions)
