"""Interact API routes — panel, survey, poll, debate, suggest endpoints."""

import asyncio
import json
import logging

from fastapi import APIRouter
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db
from forkcast.llm.factory import create_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/interact", tags=["interact"])


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class PanelRequest(BaseModel):
    simulation_id: str
    agent_ids: list[int]
    question: str


class SuggestRequest(BaseModel):
    simulation_id: str
    topic: str


# ---------------------------------------------------------------------------
# Helper: SSE streaming wrapper for sync iterators
# ---------------------------------------------------------------------------

def _stream_response(iterator_factory):
    """Wrap a sync Iterator[StreamEvent] into an SSE EventSourceResponse."""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    async def _produce():
        def _run():
            for event in iterator_factory():
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


# ---------------------------------------------------------------------------
# Panel endpoint
# ---------------------------------------------------------------------------

@router.post("/panel")
async def panel_endpoint(req: PanelRequest):
    """SSE stream of panel interview responses from multiple agents."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )

    from forkcast.interaction.panel import panel_interview

    return _stream_response(lambda: panel_interview(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.agent_ids, req.question, client, settings.domains_dir,
    ))


# ---------------------------------------------------------------------------
# Suggest endpoint
# ---------------------------------------------------------------------------

@router.post("/suggest")
async def suggest_endpoint(req: SuggestRequest):
    """Rank agents by relevance to a topic."""
    settings = get_settings()

    with get_db(settings.db_path) as conn:
        sim = conn.execute(
            "SELECT id FROM simulations WHERE id = ?", (req.simulation_id,)
        ).fetchone()
    if sim is None:
        return error(f"Simulation not found: {req.simulation_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )

    from forkcast.interaction.suggest import suggest_agents

    result = suggest_agents(
        settings.db_path, settings.data_dir,
        req.simulation_id, req.topic, client,
    )
    return success(result)
