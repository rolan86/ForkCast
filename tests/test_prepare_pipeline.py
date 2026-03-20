"""Tests for the simulation prepare pipeline orchestrator."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse
from forkcast.simulation.prepare import prepare_simulation


def _setup_db(db_path: Path, project_id: str = "proj_test1", sim_id: str = "sim_test1"):
    """Create DB with a project, graph, and simulation."""
    init_db(db_path)
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, ?, datetime('now'))",
            (f"graph_{project_id}", project_id, str(db_path.parent / project_id / "graph.json")),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, ?, 'created', 'oasis', '[\"twitter\",\"reddit\"]', datetime('now'))",
            (sim_id, project_id, f"graph_{project_id}"),
        )
    return project_id, sim_id


def _create_graph_file(data_dir: Path, project_id: str):
    """Create a minimal graph.json."""
    graph_dir = data_dir / project_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph = {
        "nodes": [
            {"id": "Dr. Smith", "type": "Researcher", "description": "AI researcher"},
            {"id": "TechCorp", "type": "Organization", "description": "Tech company"},
            {"id": "AI Ethics Board", "type": "Organization", "description": "Ethics org"},
        ],
        "edges": [
            {"source": "Dr. Smith", "target": "TechCorp", "type": "WORKS_AT"},
            {"source": "Dr. Smith", "target": "AI Ethics Board", "type": "MEMBER_OF"},
        ],
    }
    (graph_dir / "graph.json").write_text(json.dumps(graph))
    return graph


def _mock_profile_json():
    return json.dumps({
        "name": "Dr. Smith", "username": "drsmith",
        "bio": "AI researcher", "persona": "A thoughtful researcher...",
        "age": 40, "gender": "female", "profession": "Researcher",
        "interests": ["AI", "ethics"],
    })


def _mock_config_json():
    return json.dumps({
        "total_hours": 48, "minutes_per_round": 30,
        "peak_hours": [10, 11, 12], "off_peak_hours": [2, 3, 4],
        "peak_multiplier": 1.5, "off_peak_multiplier": 0.3,
        "seed_posts": ["Breaking: new policy"], "hot_topics": ["policy"],
        "narrative_direction": "Evolving debate",
        "agent_configs": [{"agent_id": 0, "activity_level": 0.8}],
        "platform_config": {"feed_weights": {"recency": 0.5}},
    })


class TestPreparePipeline:
    def test_prepare_creates_profiles_and_config(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        # Profile generation calls (think) — one per entity
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            LLMResponse(text=_mock_profile_json(), input_tokens=500, output_tokens=300),
            # Config generation call (think)
            LLMResponse(text=_mock_config_json(), input_tokens=800, output_tokens=600),
        ]

        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
        )

        assert result.profiles_count == 3
        assert result.config_generated is True
        assert result.tokens_used["input"] > 0
        # Verify profiles file exists
        profiles_path = Path(result.profiles_path)
        assert profiles_path.exists()
        profiles = json.loads(profiles_path.read_text())
        assert len(profiles) == 3

        # Verify config persisted to DB
        with get_db(tmp_db_path) as conn:
            sim = conn.execute(
                "SELECT status, config_json FROM simulations WHERE id = ?", (sim_id,)
            ).fetchone()
        assert sim["status"] == "prepared"
        assert json.loads(sim["config_json"])["total_hours"] == 48

    def test_prepare_not_found(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        init_db(tmp_db_path)
        client = MagicMock()

        with pytest.raises(ValueError, match="Simulation not found"):
            prepare_simulation(
                db_path=tmp_db_path,
                data_dir=tmp_data_dir,
                simulation_id="nonexistent",
                client=client,
                domains_dir=tmp_domains_dir,
            )

    def test_prepare_logs_token_usage(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_config_json(), input_tokens=200, output_tokens=100),
        ]

        prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
        )

        with get_db(tmp_db_path) as conn:
            usage = conn.execute(
                "SELECT * FROM token_usage WHERE project_id = ? AND stage = 'simulation_prep'",
                (project_id,),
            ).fetchone()
        assert usage is not None
        assert usage["input_tokens"] == 500  # 3*100 + 200
        assert usage["output_tokens"] == 250  # 3*50 + 100

    def test_prepare_progress_callback(self, tmp_data_dir, tmp_db_path, tmp_domains_dir):
        project_id, sim_id = _setup_db(tmp_db_path)
        _create_graph_file(tmp_data_dir, project_id)

        client = MagicMock()
        client.default_model = "claude-sonnet-4-6"
        client.think.side_effect = [
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_profile_json(), input_tokens=100, output_tokens=50),
            LLMResponse(text=_mock_config_json(), input_tokens=200, output_tokens=100),
        ]

        progress_events = []

        def on_progress(stage, **kwargs):
            progress_events.append({"stage": stage, **kwargs})

        prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=client,
            domains_dir=tmp_domains_dir,
            on_progress=on_progress,
        )

        stages = [e["stage"] for e in progress_events]
        assert "loading_graph" in stages
        assert "generating_profiles" in stages
        assert "generating_config" in stages
        assert "complete" in stages
