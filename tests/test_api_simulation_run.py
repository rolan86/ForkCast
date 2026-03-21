"""Tests for simulation run API endpoints (start, stop, stream, actions)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """Create app with initialized DB using the same pattern as other test files."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    init_db(tmp_db_path)

    from forkcast.api.app import create_app
    return create_app()


def _insert_prepared_simulation(db_path: Path, data_dir: Path) -> str:
    """Create a project, graph, and prepared simulation in the test DB."""
    project_id = "proj_test"
    graph_id = "graph_test"
    sim_id = "sim_run_test"

    config = {
        "total_hours": 1, "minutes_per_round": 60,
        "peak_hours": [10], "off_peak_hours": [0],
        "peak_multiplier": 1.5, "off_peak_multiplier": 0.3,
        "seed_posts": [], "hot_topics": ["AI"],
        "narrative_direction": "", "agent_configs": [], "platform_config": {},
    }

    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "A researcher.", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"],
         "entity_type": "Person", "entity_source": "Alice"},
    ]

    # Write profiles
    profiles_dir = data_dir / sim_id / "profiles"
    profiles_dir.mkdir(parents=True)
    (profiles_dir / "agents.json").write_text(json.dumps(profiles), encoding="utf-8")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'created', 'Test question', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, created_at) VALUES (?, ?, 'complete', datetime('now'))",
            (graph_id, project_id),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, graph_id, status, engine_type, platforms, config_json, created_at) "
            "VALUES (?, ?, ?, 'prepared', 'claude', '[\"twitter\"]', ?, datetime('now'))",
            (sim_id, project_id, graph_id, json.dumps(config)),
        )

    return sim_id


class TestStartSimulation:
    @pytest.mark.asyncio
    async def test_start_returns_immediately(self, app, tmp_db_path, tmp_data_dir):
        sim_id = _insert_prepared_simulation(tmp_db_path, tmp_data_dir)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.simulation_routes.ClaudeClient"):
                with patch("forkcast.api.simulation_routes.run_simulation"):
                    resp = await client.post(f"/api/simulations/{sim_id}/start")

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"

    @pytest.mark.asyncio
    async def test_start_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/simulations/nonexistent/start")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_start_wrong_status(self, app, tmp_db_path, tmp_data_dir):
        sim_id = _insert_prepared_simulation(tmp_db_path, tmp_data_dir)
        # Change status to 'created' (not prepared)
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'created' WHERE id = ?", (sim_id,))

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.simulation_routes.ClaudeClient"):
                resp = await client.post(f"/api/simulations/{sim_id}/start")
        assert resp.status_code == 400


class TestStopSimulation:
    @pytest.mark.asyncio
    async def test_stop_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/simulations/nonexistent/stop")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_not_running(self, app, tmp_db_path, tmp_data_dir):
        sim_id = _insert_prepared_simulation(tmp_db_path, tmp_data_dir)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/simulations/{sim_id}/stop")
        assert resp.status_code == 400


class TestRunStream:
    @pytest.mark.asyncio
    async def test_stream_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/simulations/nonexistent/run/stream")
        assert resp.status_code == 404


class TestGetSimulationActions:
    @pytest.mark.asyncio
    async def test_get_actions_empty(self, app, tmp_db_path, tmp_data_dir):
        sim_id = _insert_prepared_simulation(tmp_db_path, tmp_data_dir)
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/simulations/{sim_id}/actions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_get_actions_with_data(self, app, tmp_db_path, tmp_data_dir):
        sim_id = _insert_prepared_simulation(tmp_db_path, tmp_data_dir)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO simulation_actions (simulation_id, round, agent_id, agent_name, action_type, content, platform, timestamp) "
                "VALUES (?, 1, 0, 'alice', 'CREATE_POST', '{\"content\": \"Hello\"}', 'twitter', '2026-03-20T10:00:00Z')",
                (sim_id,),
            )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/simulations/{sim_id}/actions")
        data = resp.json()
        assert len(data["data"]) == 1
        assert data["data"][0]["action_type"] == "CREATE_POST"
