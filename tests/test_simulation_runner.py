"""Tests for simulation runner orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.action import Action, ActionType
from forkcast.simulation.models import (
    AgentProfile,
    RunResult,
    SimulationConfig,
)
from forkcast.simulation.runner import run_simulation


def _setup_db(db_path, data_dir, domains_dir):
    """Set up a test database with project, graph, and prepared simulation."""
    init_db(db_path)

    project_id = "proj_test"
    graph_id = "graph_test"
    sim_id = "sim_test"

    profiles = [
        AgentProfile(
            agent_id=0, name="Alice", username="alice", bio="AI researcher",
            persona="A thoughtful researcher focused on AI safety.",
            age=32, gender="female", profession="Researcher",
            interests=["AI", "ethics"], entity_type="Person", entity_source="Alice Smith",
        ),
        AgentProfile(
            agent_id=1, name="Bob", username="bob", bio="Tech CEO",
            persona="A bold tech leader pushing for rapid AI adoption.",
            age=45, gender="male", profession="CEO",
            interests=["startups", "AI"], entity_type="Person", entity_source="Bob Jones",
        ),
    ]

    config = SimulationConfig(
        total_hours=1, minutes_per_round=60,
        peak_hours=[10], off_peak_hours=[0, 1, 2],
        peak_multiplier=1.5, off_peak_multiplier=0.3,
        seed_posts=["What does AI mean?"], hot_topics=["AI safety"],
        narrative_direction="Explore", agent_configs=[], platform_config={},
    )

    # Write profiles
    sim_dir = data_dir / sim_id / "profiles"
    sim_dir.mkdir(parents=True)
    (sim_dir / "agents.json").write_text(
        json.dumps([p.to_dict() for p in profiles]), encoding="utf-8"
    )

    # Set up domain prompts
    default_domain = domains_dir / "_default"
    default_domain.mkdir(parents=True, exist_ok=True)
    (default_domain / "manifest.yaml").write_text(
        "name: _default\nversion: '1.0'\ndescription: Default\nlanguage: en\n"
        "sim_engine: claude\nplatforms: [twitter, reddit]\n"
    )
    prompts_dir = default_domain / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    (prompts_dir / "agent_system.md").write_text(
        "You are {{ agent_name }}. {{ persona }}"
    )
    for name in ["ontology.md", "persona.md", "report_guidelines.md", "config_gen.md"]:
        (prompts_dir / name).write_text(f"# {name}\nPlaceholder.\n")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Predict AI trends', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) "
            "VALUES (?, ?, 'complete', datetime('now'))",
            (graph_id, project_id),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, project_id, graph_id, json.dumps(config.to_dict())),
        )

    return sim_id, project_id


class TestRunSimulation:
    def test_run_produces_result(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, project_id = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Hello"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        progress = []
        result = run_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: progress.append(kw),
        )

        assert isinstance(result, RunResult)
        assert result.simulation_id == sim_id
        assert result.actions_count > 0

    def test_run_writes_actions_jsonl(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "Test"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        jsonl_path = tmp_data_dir / sim_id / "actions.jsonl"
        assert jsonl_path.exists()
        lines = jsonl_path.read_text().strip().split("\n")
        assert len(lines) > 0
        action = json.loads(lines[0])
        assert "action_type" in action
        assert "agent_id" in action

    def test_run_updates_db_status(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            sim = conn.execute("SELECT status FROM simulations WHERE id = ?", (sim_id,)).fetchone()
            assert sim["status"] == "completed"

    def test_run_inserts_actions_to_db(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "create_post", "input": {"content": "DB test"}}],
            input_tokens=100, output_tokens=50,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM simulation_actions WHERE simulation_id = ?", (sim_id,)
            ).fetchone()[0]
            assert count > 0

    def test_run_emits_progress_events(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        sim_id, _ = _setup_db(tmp_db_path, tmp_data_dir, tmp_domains_dir)

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.tool_use.return_value = LLMResponse(
            text="",
            tool_calls=[{"id": "1", "name": "do_nothing", "input": {"reason": "quiet"}}],
            input_tokens=50, output_tokens=30,
            model="claude-sonnet-4-6", stop_reason="tool_use",
        )

        events = []
        run_simulation(
            db_path=tmp_db_path, data_dir=tmp_data_dir, simulation_id=sim_id,
            client=mock_client, domains_dir=tmp_domains_dir,
            on_progress=lambda **kw: events.append(kw),
        )

        stages = [e.get("stage") for e in events]
        assert "loading" in stages
        assert "running" in stages or "round" in stages
        assert "complete" in stages
