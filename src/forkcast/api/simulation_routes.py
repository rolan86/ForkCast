"""Simulation management API routes with SSE streaming."""

import asyncio
import json
import logging
import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.prepare import prepare_simulation

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
    loop = asyncio.get_event_loop()

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
