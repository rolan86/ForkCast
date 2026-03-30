"""Tests for simulation API routes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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


def _insert_project_with_graph(db_path: Path, project_id: str = "proj_test1"):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, created_at) "
            "VALUES (?, ?, 'complete', 5, 3, datetime('now'))",
            (f"graph_{project_id}", project_id),
        )
    return project_id


class TestCreateSimulation:
    @pytest.mark.asyncio
    async def test_create_simulation(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
                "engine_type": "oasis",
                "platforms": ["twitter", "reddit"],
            })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["project_id"] == project_id
        assert data["engine_type"] == "oasis"
        assert data["status"] == "created"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_simulation_project_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": "nonexistent",
                "engine_type": "oasis",
                "platforms": ["twitter"],
            })
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_create_simulation_defaults(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
            })

        assert response.status_code == 201
        data = response.json()["data"]
        # engine_type now comes from _default domain manifest (sim_engine: claude)
        assert data["engine_type"] == "claude"
        assert data["platforms"] == ["twitter", "reddit"]


class TestTriggerPrepare:
    @pytest.mark.asyncio
    async def test_trigger_prepare_returns_immediately(self, app, tmp_db_path):
        """POST /prepare should return immediately with status 'preparing'."""
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={"project_id": project_id})
            sim_id = create_resp.json()["data"]["id"]

            with patch("forkcast.api.simulation_routes.create_llm_client"):
                with patch("forkcast.api.simulation_routes.prepare_simulation"):
                    response = await client.post(f"/api/simulations/{sim_id}/prepare")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "preparing"
        assert data["simulation_id"] == sim_id

    @pytest.mark.asyncio
    async def test_trigger_prepare_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations/nonexistent/prepare")
        assert response.status_code == 404


class TestGetSimulation:
    @pytest.mark.asyncio
    async def test_get_simulation(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={"project_id": project_id})
            sim_id = create_resp.json()["data"]["id"]

            response = await client.get(f"/api/simulations/{sim_id}")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == sim_id
        assert data["status"] == "created"

    @pytest.mark.asyncio
    async def test_get_simulation_not_found(self, app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/simulations/nonexistent")
        assert response.status_code == 404


class TestListSimulations:
    @pytest.mark.asyncio
    async def test_list_simulations(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/simulations", json={"project_id": project_id})
            response = await client.get("/api/simulations")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_list_simulations_includes_agent_mode(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/api/simulations", json={
                "project_id": project_id,
                "agent_mode": "native",
            })
            response = await client.get("/api/simulations")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) >= 1
        assert data[0]["agent_mode"] == "native"


class TestPrepModel:
    @pytest.mark.asyncio
    async def test_create_simulation_with_prep_model(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
                "prep_model": "claude-haiku-4-5",
            })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["prep_model"] == "claude-haiku-4-5"

    @pytest.mark.asyncio
    async def test_prep_model_persisted_in_db(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={
                "project_id": project_id,
                "prep_model": "claude-haiku-4-5",
            })
            assert create_resp.status_code == 201
            sim_id = create_resp.json()["data"]["id"]

            get_resp = await client.get(f"/api/simulations/{sim_id}")

        assert get_resp.status_code == 200
        assert get_resp.json()["data"]["prep_model"] == "claude-haiku-4-5"

    @pytest.mark.asyncio
    async def test_create_simulation_without_prep_model_defaults_to_none(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
            })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["prep_model"] is None


class TestAgentMode:
    @pytest.mark.asyncio
    async def test_create_with_agent_mode_native(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
                "agent_mode": "native",
            })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["agent_mode"] == "native"

    @pytest.mark.asyncio
    async def test_create_without_agent_mode_defaults_to_llm(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
            })

        assert response.status_code == 201
        data = response.json()["data"]
        assert data["agent_mode"] == "llm"

    @pytest.mark.asyncio
    async def test_create_with_invalid_agent_mode(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/api/simulations", json={
                "project_id": project_id,
                "agent_mode": "invalid_mode",
            })

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_settings_agent_mode(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={
                "project_id": project_id,
            })
            sim_id = create_resp.json()["data"]["id"]

            response = await client.patch(f"/api/simulations/{sim_id}/settings", json={
                "agent_mode": "native",
            })

        assert response.status_code == 200
        assert response.json()["data"]["updated"] is True

    @pytest.mark.asyncio
    async def test_update_settings_invalid_agent_mode(self, app, tmp_db_path):
        project_id = _insert_project_with_graph(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            create_resp = await client.post("/api/simulations", json={
                "project_id": project_id,
            })
            sim_id = create_resp.json()["data"]["id"]

            response = await client.patch(f"/api/simulations/{sim_id}/settings", json={
                "agent_mode": "bogus",
            })

        assert response.status_code == 400
