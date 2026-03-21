"""Report generation and chat API routes with SSE streaming."""

import asyncio
import json
import logging
import secrets
from typing import Optional

from fastapi import APIRouter, Query
from fastapi.responses import Response
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.client import ClaudeClient
from forkcast.report.agent_chat import agent_chat
from forkcast.report.chat import report_chat
from forkcast.report.pipeline import generate_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["reports", "chat"])

# Per-report generation progress queues
_generate_queues: dict[str, asyncio.Queue] = {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class GenerateReportRequest(BaseModel):
    simulation_id: str
    max_tool_rounds: int = 10


class ChatReportRequest(BaseModel):
    report_id: str
    message: str


class ChatAgentRequest(BaseModel):
    simulation_id: str
    agent_id: int
    message: str


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------

@router.get("/reports")
async def list_reports(simulation_id: Optional[str] = Query(default=None)):
    """List all reports, optionally filtered by simulation_id."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        if simulation_id is not None:
            rows = conn.execute(
                "SELECT id, simulation_id, status, content_markdown, created_at, completed_at "
                "FROM reports WHERE simulation_id = ? ORDER BY created_at DESC",
                (simulation_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, simulation_id, status, content_markdown, created_at, completed_at "
                "FROM reports ORDER BY created_at DESC"
            ).fetchall()

    return success([dict(row) for row in rows])


@router.post("/reports/generate")
async def generate_report_endpoint(req: GenerateReportRequest):
    """Start background report generation; returns report_id immediately.

    Monitor progress via GET /api/reports/{report_id}/generate/stream (SSE).
    """
    settings = get_settings()

    # Verify simulation exists
    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    # Pre-allocate a report_id so the caller has it immediately
    report_id = f"report_{secrets.token_hex(8)}"

    queue: asyncio.Queue = asyncio.Queue()
    _generate_queues[report_id] = queue
    loop = asyncio.get_running_loop()

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    async def _run():
        try:
            result = await asyncio.to_thread(
                generate_report,
                settings.db_path,
                settings.data_dir,
                req.simulation_id,
                client,
                settings.domains_dir,
                on_progress=lambda **kw: loop.call_soon_threadsafe(queue.put_nowait, kw),
                max_tool_rounds=req.max_tool_rounds,
                report_id=report_id,
            )
            await queue.put({
                "stage": "result",
                "report_id": result.report_id,
                "simulation_id": result.simulation_id,
                "tool_rounds": result.tool_rounds,
                "tokens_used": result.tokens_used,
            })
        except Exception as exc:
            logger.exception(f"Report generation failed for simulation {req.simulation_id}")
            await queue.put({"stage": "error", "message": str(exc)})
        finally:
            await queue.put(None)  # sentinel

    asyncio.create_task(_run())

    return success({"report_id": report_id, "status": "generating", "simulation_id": req.simulation_id})


@router.get("/reports/{report_id}/generate/stream")
async def stream_generate(report_id: str):
    """SSE stream for report generation progress."""
    queue = _generate_queues.get(report_id)
    if queue is None:
        return error("No generation job running for this report", status_code=404)

    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue

            if event is None:
                yield {"event": "complete", "data": "{}"}
                _generate_queues.pop(report_id, None)
                break

            yield {"event": event.get("stage", "progress"), "data": json.dumps(event)}

    return EventSourceResponse(event_generator())


@router.get("/reports/{report_id}/export")
async def export_report(report_id: str):
    """Download report as raw markdown."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, content_markdown FROM reports WHERE id = ?", (report_id,)
        ).fetchone()

    if row is None:
        return error(f"Report not found: {report_id}", status_code=404)

    content = row["content_markdown"] or ""
    filename = f"{report_id}.md"
    return Response(
        content=content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports/{report_id}")
async def get_report(report_id: str):
    """Get a single report by ID."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, simulation_id, status, content_markdown, tool_history_json, "
            "created_at, completed_at FROM reports WHERE id = ?",
            (report_id,),
        ).fetchone()

    if row is None:
        return error(f"Report not found: {report_id}", status_code=404)

    d = dict(row)
    if d.get("tool_history_json"):
        try:
            d["tool_history"] = json.loads(d["tool_history_json"])
        except json.JSONDecodeError:
            d["tool_history"] = []
    else:
        d["tool_history"] = []
    d.pop("tool_history_json", None)
    return success(d)


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@router.post("/chat/report")
async def chat_with_report(req: ChatReportRequest):
    """SSE stream of report_chat() events."""
    settings = get_settings()
    client = ClaudeClient(api_key=settings.anthropic_api_key)

    report_id = req.report_id
    message = req.message

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def _produce():
        def _run():
            for event in report_chat(
                settings.db_path,
                settings.data_dir,
                report_id,
                message,
                client,
                settings.domains_dir,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        await asyncio.to_thread(_run)

    asyncio.create_task(_produce())

    async def _event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {"event": event.type, "data": json.dumps(event.data, default=str)}

    return EventSourceResponse(_event_generator())


@router.post("/chat/agent")
async def chat_with_agent(req: ChatAgentRequest):
    """SSE stream of agent_chat() events."""
    settings = get_settings()

    # Verify simulation exists
    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()

    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = ClaudeClient(api_key=settings.anthropic_api_key)

    simulation_id = req.simulation_id
    agent_id = req.agent_id
    message = req.message

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def _produce():
        def _run():
            for event in agent_chat(
                settings.db_path,
                settings.data_dir,
                simulation_id,
                agent_id,
                message,
                client,
                settings.domains_dir,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, event)
            loop.call_soon_threadsafe(queue.put_nowait, None)
        await asyncio.to_thread(_run)

    asyncio.create_task(_produce())

    async def _event_generator():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield {"event": event.type, "data": json.dumps(event.data, default=str)}

    return EventSourceResponse(_event_generator())
