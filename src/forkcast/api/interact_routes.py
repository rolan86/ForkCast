"""Interact API routes — panel, survey, poll, debate, suggest endpoints."""

import asyncio
import json
import logging
from typing import Optional

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


class SurveyRequest(BaseModel):
    simulation_id: str
    question: str
    agent_ids: Optional[list[int]] = None


class PollRequest(BaseModel):
    simulation_id: str
    question: str
    options: list[str]
    agent_ids: Optional[list[int]] = None


class DebateRequest(BaseModel):
    simulation_id: str
    agent_id_pro: int
    agent_id_con: int
    topic: str
    rounds: int = 5
    mode: str = "autoplay"  # "autoplay" | "moderated"


class DebateContinueRequest(BaseModel):
    simulation_id: str
    debate_id: str
    interjection: str


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


# ---------------------------------------------------------------------------
# Survey endpoint
# ---------------------------------------------------------------------------

@router.post("/survey")
async def survey_endpoint(req: SurveyRequest):
    """SSE stream of free-text survey responses + AI summary."""
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

    from forkcast.interaction.survey import free_text_survey

    return _stream_response(lambda: free_text_survey(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.question, req.agent_ids, client, settings.domains_dir,
    ))


# ---------------------------------------------------------------------------
# Poll endpoint
# ---------------------------------------------------------------------------

@router.post("/poll")
async def poll_endpoint(req: PollRequest):
    """Run structured poll — returns results with choices and summary."""
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

    from forkcast.interaction.poll import structured_poll

    result = structured_poll(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.question, req.options, req.agent_ids, client, settings.domains_dir,
    )
    return success(result)


# ---------------------------------------------------------------------------
# Debate endpoints
# ---------------------------------------------------------------------------

# In-memory debate state for moderated mode (keyed by debate_id)
_debate_state: dict[str, dict] = {}


@router.post("/debate")
async def debate_endpoint(req: DebateRequest):
    """SSE stream of debate rounds between two agents."""
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

    # For moderated mode, store debate state
    if req.mode == "moderated":
        import time

        debate_id = f"debate_{req.simulation_id}_{int(time.time())}"
        _debate_state[debate_id] = {
            "simulation_id": req.simulation_id,
            "agent_id_pro": req.agent_id_pro,
            "agent_id_con": req.agent_id_con,
            "topic": req.topic,
            "rounds": req.rounds,
            "history": [],
            "current_round": 1,
        }

    from forkcast.interaction.debate import run_debate

    return _stream_response(lambda: run_debate(
        settings.db_path, settings.data_dir, req.simulation_id,
        req.agent_id_pro, req.agent_id_con, req.topic,
        req.rounds, req.mode, client, settings.domains_dir,
    ))


@router.post("/debate/continue")
async def debate_continue_endpoint(req: DebateContinueRequest):
    """SSE stream of next debate round with moderator interjection."""
    settings = get_settings()

    state = _debate_state.get(req.debate_id)
    if state is None:
        return error(f"Debate not found: {req.debate_id}", status_code=404)

    client = create_llm_client(
        provider=settings.llm_provider,
        api_key=settings.anthropic_api_key,
        ollama_base_url=settings.ollama_base_url,
        ollama_model=settings.ollama_model,
    )

    from forkcast.interaction.debate import run_debate

    return _stream_response(lambda: run_debate(
        settings.db_path, settings.data_dir, state["simulation_id"],
        state["agent_id_pro"], state["agent_id_con"], state["topic"],
        state["rounds"], "moderated", client, settings.domains_dir,
        interjection=req.interjection,
        debate_history=state["history"],
        current_round=state["current_round"],
    ))
