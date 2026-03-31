"""Tests for interact API routes."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.config import reset_settings
from forkcast.db.connection import init_db, get_db
from forkcast.llm.client import LLMResponse


@pytest.fixture
def app(tmp_db_path, tmp_data_dir, tmp_domains_dir):
    os.environ["FORKCAST_DATA_DIR"] = str(tmp_data_dir)
    os.environ["FORKCAST_DOMAINS_DIR"] = str(tmp_domains_dir)
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    reset_settings()
    init_db(tmp_db_path)
    from forkcast.api.app import create_app
    return create_app()


@pytest.fixture
def setup_sim(tmp_db_path, tmp_data_dir):
    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1','_default','T','ready','R',datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, config_json) "
            "VALUES ('sim1', 'p1', 'prepared', '{}')"
        )
    profiles_dir = tmp_data_dir / "sim1" / "profiles"
    profiles_dir.mkdir(parents=True)
    profiles = [
        {"agent_id": 0, "name": "Alice", "username": "alice", "bio": "Test",
         "persona": "Researcher", "age": 30, "gender": "female",
         "profession": "Researcher", "interests": ["AI"], "entity_type": "Person",
         "entity_source": "test"},
    ]
    (profiles_dir / "agents.json").write_text(json.dumps(profiles))


class TestInteractRoutes:
    @pytest.mark.asyncio
    async def test_suggest_agents(self, app, setup_sim):
        mock_response = LLMResponse(
            text=json.dumps({"suggestions": [{"agent_id": 0, "reason": "Relevant"}]}),
            input_tokens=10, output_tokens=5,
        )
        with patch("forkcast.api.interact_routes.create_llm_client") as mock_factory:
            mock_client = MagicMock()
            mock_client.complete.return_value = mock_response
            mock_factory.return_value = mock_client

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
                resp = await ac.post("/api/interact/suggest", json={
                    "simulation_id": "sim1",
                    "topic": "AI trust",
                })
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert len(data["data"]["suggestions"]) == 1

    @pytest.mark.asyncio
    async def test_suggest_sim_not_found(self, app, setup_sim):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.post("/api/interact/suggest", json={
                "simulation_id": "missing",
                "topic": "AI trust",
            })
            assert resp.status_code == 404
            data = resp.json()
            assert data["success"] is False
