"""Simulation management API routes with SSE streaming."""

import asyncio
import json
import logging
import secrets
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.prepare import prepare_simulation
from forkcast.simulation.runner import run_simulation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulations", tags=["simulations"])

# Per-simulation progress queues. Created on POST /prepare, consumed by GET /prepare/stream.
_prepare_queues: dict[str, asyncio.Queue] = {}


class CreateSimulationRequest(BaseModel):
    project_id: str
    engine_type: str = "oasis"
    platforms: list[str] = ["twitter", "reddit"]


@router.post("")
async def create_simulation(req: CreateSimulationRequest):
    """Create a new simulation for a project."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (req.project_id,)
        ).fetchone()

    if project is None:
        return error(f"Project not found: {req.project_id}", status_code=404)

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
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', ?, ?, ?)",
            (sim_id, req.project_id, graph_id, req.engine_type, json.dumps(req.platforms), now),
        )

    return success(
        {
            "id": sim_id,
            "project_id": req.project_id,
            "graph_id": graph_id,
            "status": "created",
            "engine_type": req.engine_type,
            "platforms": req.platforms,
            "created_at": now,
        },
        status_code=201,
    )


@router.get("")
async def list_simulations():
    """List all simulations."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, project_id, graph_id, status, engine_type, platforms, created_at, updated_at "
            "FROM simulations ORDER BY created_at DESC"
        ).fetchall()

    results = []
    for row in rows:
        d = dict(row)
        d["platforms"] = json.loads(d["platforms"]) if d["platforms"] else []
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


@router.post("/{simulation_id}/prepare")
async def trigger_prepare(simulation_id: str):
    """Trigger simulation preparation as a background task.

    Returns immediately with status 'preparing'. Monitor progress via
    GET /api/simulations/{id}/prepare/stream (SSE).
    """
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id, status FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {simulation_id}", status_code=404)

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
    if sim["status"] != "prepared":
        return error(f"Simulation must be in 'prepared' status to start (current: {sim['status']})", status_code=400)

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
