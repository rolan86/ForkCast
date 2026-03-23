"""Integration test: full simulation create + prepare flow."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.db.connection import get_db, init_db
from forkcast.llm.client import LLMResponse


def _mock_profile():
    return json.dumps({
        "name": "Agent X", "username": "agentx",
        "bio": "Test agent", "persona": "A test persona",
        "age": 30, "gender": "other", "profession": "Tester",
        "interests": ["testing"],
    })


def _mock_config():
    return json.dumps({
        "total_hours": 24, "minutes_per_round": 15,
        "peak_hours": [10, 11], "off_peak_hours": [2, 3],
        "peak_multiplier": 1.2, "off_peak_multiplier": 0.5,
        "seed_posts": ["Test post"], "hot_topics": ["testing"],
        "narrative_direction": "Test direction",
        "agent_configs": [{"agent_id": 0, "activity_level": 0.5}],
        "platform_config": {"feed_weights": {"recency": 0.5}},
    })


class TestFullPrepareFlow:
    @pytest.mark.asyncio
    async def test_create_sim_then_prepare_pipeline(self, tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
        """Integration test: create sim via API, then run prepare pipeline directly."""
        monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
        monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from forkcast.config import reset_settings
        reset_settings()

        init_db(tmp_db_path)
        project_id = "proj_integ"

        # Setup: project + graph + graph file
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, '_default', 'Integration', 'graph_built', 'Test prediction', datetime('now'))",
                (project_id,),
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
                "VALUES (?, ?, 'complete', 2, 1, ?, datetime('now'))",
                (f"graph_{project_id}", project_id, str(tmp_data_dir / project_id / "graph.json")),
            )

        graph_dir = tmp_data_dir / project_id
        graph_dir.mkdir(parents=True, exist_ok=True)
        (graph_dir / "graph.json").write_text(json.dumps({
            "nodes": [
                {"id": "Alice", "type": "Person", "description": "Engineer"},
                {"id": "Bob", "type": "Person", "description": "Manager"},
            ],
            "edges": [
                {"source": "Alice", "target": "Bob", "type": "REPORTS_TO"},
            ],
        }))

        mock_client = MagicMock()
        mock_client.default_model = "claude-sonnet-4-6"
        mock_client.smart_call.side_effect = [
            LLMResponse(text=_mock_profile(), input_tokens=200, output_tokens=100),
            LLMResponse(text=_mock_profile(), input_tokens=200, output_tokens=100),
            LLMResponse(text=_mock_config(), input_tokens=400, output_tokens=200),
        ]

        from forkcast.api.app import create_app
        app = create_app()

        # Step 1: Create simulation via API
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={
                "project_id": project_id,
                "engine_type": "claude",
                "platforms": ["twitter"],
            })
        assert create_resp.status_code == 201
        sim_id = create_resp.json()["data"]["id"]

        # Step 2: Run prepare pipeline directly (the API fires this as background task)
        from forkcast.simulation.prepare import prepare_simulation
        result = prepare_simulation(
            db_path=tmp_db_path,
            data_dir=tmp_data_dir,
            simulation_id=sim_id,
            client=mock_client,
            domains_dir=tmp_domains_dir,
        )

        assert result.profiles_count == 2
        assert result.config_generated is True

        # Verify: profiles file exists
        profiles_path = tmp_data_dir / sim_id / "profiles" / "agents.json"
        assert profiles_path.exists()
        profiles = json.loads(profiles_path.read_text())
        assert len(profiles) == 2

        # Verify: simulation status updated
        with get_db(tmp_db_path) as conn:
            sim = conn.execute(
                "SELECT status, config_json FROM simulations WHERE id = ?", (sim_id,)
            ).fetchone()
        assert sim["status"] == "prepared"
        config = json.loads(sim["config_json"])
        assert config["total_hours"] == 24

        # Verify: token usage logged
        with get_db(tmp_db_path) as conn:
            usage = conn.execute(
                "SELECT * FROM token_usage WHERE project_id = ? AND stage = 'simulation_prep'",
                (project_id,),
            ).fetchone()
        assert usage is not None
        assert usage["input_tokens"] == 800  # 2*200 + 400
        assert usage["output_tokens"] == 400  # 2*100 + 200
