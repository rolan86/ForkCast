"""Graph pipeline API routes with SSE streaming."""

import asyncio
import json
import logging
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.graph.pipeline import build_graph_pipeline
from forkcast.llm.client import ClaudeClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/projects", tags=["graph"])

_progress_queues: dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)


@router.post("/{project_id}/build-graph")
async def trigger_build_graph(project_id: str):
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id, status FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

    if project is None:
        return error(f"Project not found: {project_id}", status_code=404)

    client = ClaudeClient(api_key=settings.anthropic_api_key)
    queue = _progress_queues[project_id]

    def on_progress(stage: str, **kwargs):
        event = {"stage": stage, **kwargs}
        queue.put_nowait(event)

    def _run_pipeline():
        return build_graph_pipeline(
            db_path=settings.db_path,
            data_dir=settings.data_dir,
            project_id=project_id,
            client=client,
            domains_dir=settings.domains_dir,
            on_progress=on_progress,
        )

    try:
        result = await asyncio.to_thread(_run_pipeline)
    except Exception as e:
        logger.exception(f"Graph build failed for {project_id}")
        queue.put_nowait({"stage": "error", "message": str(e)})
        return error(f"Graph build failed: {str(e)}", status_code=500)
    finally:
        queue.put_nowait(None)

    return success(result)


@router.get("/{project_id}/build-graph/stream")
async def stream_build_graph(project_id: str, request: Request):
    queue = _progress_queues[project_id]

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
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/{project_id}/graph")
async def get_graph(project_id: str):
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        project = conn.execute(
            "SELECT id FROM projects WHERE id = ?", (project_id,)
        ).fetchone()

        if project is None:
            return error(f"Project not found: {project_id}", status_code=404)

        graph = conn.execute(
            "SELECT * FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()

    if graph is None:
        return error("No graph built for this project", status_code=404)

    return success(dict(graph))


@router.get("/{project_id}/graph/data")
async def get_graph_data(project_id: str):
    """Return graph nodes and edges in D3-friendly format."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT file_path FROM graphs WHERE project_id = ? ORDER BY created_at DESC LIMIT 1",
            (project_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No graph found for project")

    graph_path = Path(row["file_path"])
    if not graph_path.exists():
        raise HTTPException(status_code=404, detail="Graph file not found")

    raw = json.loads(graph_path.read_text())
    nodes = [
        {
            "id": n.get("name", n.get("id", "")),
            "type": n.get("type", ""),
            "description": n.get("description", ""),
        }
        for n in raw.get("nodes", [])
    ]
    edges = [
        {
            "source": e["source"],
            "target": e["target"],
            "label": e.get("type", e.get("label", "")),
        }
        for e in raw.get("edges", raw.get("links", []))
    ]
    return success({"nodes": nodes, "edges": edges})
