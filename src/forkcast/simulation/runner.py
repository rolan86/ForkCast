"""Orchestrate simulation execution: load config, select engine, run, persist."""

import dataclasses
import json
import logging
import threading
from pathlib import Path
from typing import Any, Callable

from forkcast.db.connection import get_db
from forkcast.domains.loader import load_domain, read_prompt
from forkcast.llm.client import ClaudeClient
from forkcast.simulation.action import Action
from forkcast.simulation.claude_engine import ClaudeEngine
from forkcast.simulation.models import AgentProfile, RunResult, SimulationConfig

logger = logging.getLogger(__name__)

ProgressCallback = Callable[..., None] | None

# Domain prompt key for agent system prompt
AGENT_SYSTEM_PROMPT_KEY = "agent_system"


def run_simulation(
    db_path: Path,
    data_dir: Path,
    simulation_id: str,
    client: ClaudeClient,
    domains_dir: Path,
    on_progress: ProgressCallback = None,
    max_rounds: int | None = None,
    stop_event: threading.Event | None = None,
) -> RunResult:
    """Run a simulation end-to-end.

    1. Load simulation, config, profiles from DB/disk
    2. Select engine based on engine_type
    3. Run simulation, writing each action to JSONL + SQLite
    4. Update simulation status to 'completed'
    5. Log token usage

    Args:
        max_rounds: If set, overrides total_hours to limit rounds (non-destructive).
        stop_event: If set, the engine checks this event to stop gracefully.
    """

    def _progress(stage: str, **kwargs: Any) -> None:
        if on_progress:
            on_progress(stage=stage, **kwargs)

    # 1. Load simulation record
    _progress(stage="loading")
    with get_db(db_path) as conn:
        sim = conn.execute(
            "SELECT * FROM simulations WHERE id = ?", (simulation_id,)
        ).fetchone()

    if sim is None:
        raise ValueError(f"Simulation not found: {simulation_id}")
    if sim["status"] != "prepared":
        raise ValueError(f"Simulation not in 'prepared' status: {sim['status']}")

    project_id = sim["project_id"]
    engine_type = sim["engine_type"]
    platforms = json.loads(sim["platforms"]) if sim["platforms"] else ["twitter"]

    # Load config -- filter to known fields to handle extra keys gracefully
    config_data = json.loads(sim["config_json"])
    known_fields = {f.name for f in dataclasses.fields(SimulationConfig)}
    config = SimulationConfig(**{k: v for k, v in config_data.items() if k in known_fields})

    # Non-destructive max_rounds override: adjust total_hours in memory only
    if max_rounds is not None:
        config.total_hours = max(1, (max_rounds * config.minutes_per_round) / 60)

    # Load profiles
    profiles_path = data_dir / simulation_id / "profiles" / "agents.json"
    if not profiles_path.exists():
        raise FileNotFoundError(f"Profiles not found: {profiles_path}")
    profiles = [AgentProfile(**p) for p in json.loads(profiles_path.read_text(encoding="utf-8"))]

    # Load domain for agent system prompt
    with get_db(db_path) as conn:
        project = conn.execute("SELECT domain FROM projects WHERE id = ?", (project_id,)).fetchone()
    domain = load_domain(project["domain"], domains_dir)

    # Update status to running
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'running', updated_at = datetime('now') WHERE id = ?",
            (simulation_id,),
        )

    # 2. Set up JSONL output
    sim_dir = data_dir / simulation_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    actions_path = sim_dir / "actions.jsonl"
    actions_file = open(actions_path, "w", encoding="utf-8")
    all_actions: list[Action] = []

    def on_action(action: Action) -> None:
        all_actions.append(action)
        actions_file.write(action.to_jsonl() + "\n")
        actions_file.flush()
        _progress(stage="action", **action.to_dict())

    def on_round(round_num: int, total: int) -> None:
        _progress(stage="round", current=round_num, total=total)

    # 3. Select and run engine
    engine_result: dict[str, Any] = {}
    total_tokens: dict[str, int] = {"input": 0, "output": 0}
    try:
        if engine_type == "claude":
            # Try to load agent_system prompt; fall back to a minimal default
            try:
                agent_system_template = read_prompt(domain, AGENT_SYSTEM_PROMPT_KEY)
            except FileNotFoundError:
                agent_system_template = "You are {{ agent_name }}. {{ persona }}"

            _progress(stage="running", engine="claude", total_rounds=0)

            # Run once per platform
            for platform in platforms:
                if stop_event is not None and stop_event.is_set():
                    break

                engine = ClaudeEngine(client=client, agent_system_template=agent_system_template)

                # Wire stop_event into on_round callback
                round_cb = on_round
                if stop_event is not None:
                    def round_cb(r, t, eng=engine):
                        if stop_event.is_set():
                            eng.stop()
                        _progress(stage="round", current=r, total=t)

                engine_result = engine.run(
                    profiles=profiles,
                    config=config,
                    platform=platform,
                    on_action=on_action,
                    on_round=round_cb,
                )
                total_tokens["input"] += engine_result.get("input_tokens", 0)
                total_tokens["output"] += engine_result.get("output_tokens", 0)

        elif engine_type == "oasis":
            # Deferred import -- OASIS is an optional dependency
            from forkcast.simulation.oasis_engine import OasisEngine

            _progress(stage="running", engine="oasis")
            for platform in platforms:
                if stop_event is not None and stop_event.is_set():
                    break

                oasis_engine = OasisEngine(sim_dir=sim_dir)
                # Wire stop_event: spawn a monitor thread that checks the event
                if stop_event is not None:
                    def _oasis_stop_monitor(eng=oasis_engine):
                        stop_event.wait()
                        eng.stop()

                    stop_thread = threading.Thread(target=_oasis_stop_monitor, daemon=True)
                    stop_thread.start()
                engine_result = oasis_engine.run(
                    profiles=profiles,
                    config=config,
                    platform=platform,
                    on_action=on_action,
                    on_round=on_round,
                )
        else:
            raise ValueError(f"Unknown engine type: {engine_type}")
    finally:
        actions_file.close()

    # 4. Persist actions to SQLite
    with get_db(db_path) as conn:
        for action in all_actions:
            conn.execute(
                "INSERT INTO simulation_actions "
                "(simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    simulation_id,
                    action.round,
                    action.agent_id,
                    action.agent_name,
                    action.action_type,
                    json.dumps(action.action_args),
                    action.platform,
                    action.timestamp,
                ),
            )

    # 5. Update status
    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE simulations SET status = 'completed', updated_at = datetime('now') WHERE id = ?",
            (simulation_id,),
        )

    # 6. Log token usage
    if engine_type == "claude" and (total_tokens["input"] > 0 or total_tokens["output"] > 0):
        with get_db(db_path) as conn:
            conn.execute(
                "INSERT INTO token_usage (project_id, stage, model, input_tokens, output_tokens, created_at) "
                "VALUES (?, 'simulation_run', ?, ?, ?, datetime('now'))",
                (project_id, client.default_model, total_tokens["input"], total_tokens["output"]),
            )

    _progress(stage="complete", actions_count=len(all_actions))

    return RunResult(
        simulation_id=simulation_id,
        actions_count=len(all_actions),
        total_rounds=engine_result.get("total_rounds", 0),
        actions_path=str(actions_path),
        tokens_used=total_tokens if engine_type == "claude" else {},
    )
