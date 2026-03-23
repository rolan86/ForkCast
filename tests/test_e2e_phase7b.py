"""End-to-end tests for Phase 7b: settings, capabilities, resume endpoints."""

import json
import pytest
from httpx import ASGITransport, AsyncClient
from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    from forkcast.config import reset_settings
    reset_settings()
    return create_app()


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _create_project(db_path):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
        )


class TestCapabilitiesE2E:
    @pytest.mark.anyio
    async def test_capabilities_endpoint_exists(self, client):
        resp = await client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "claude" in data["data"]["engines"]

    @pytest.mark.anyio
    async def test_capabilities_has_models(self, client):
        resp = await client.get("/api/capabilities")
        data = resp.json()["data"]
        assert len(data["models"]) > 0
        for m in data["models"]:
            assert "id" in m
            assert "label" in m
            assert "supports_thinking" in m


class TestSettingsE2E:
    @pytest.mark.anyio
    async def test_full_settings_workflow(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        # Create
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim = resp.json()["data"]
        sim_id = sim["id"]
        # Default engine from domain (claude)
        assert sim["engine_type"] == "claude"
        # Patch
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "platforms": ["twitter"],
            "prep_model": "claude-haiku-4-5",
        })
        assert resp.status_code == 200
        # Verify
        resp = await client.get(f"/api/simulations/{sim_id}")
        d = resp.json()["data"]
        assert d["platforms"] == ["twitter"]
        assert d["prep_model"] == "claude-haiku-4-5"

    @pytest.mark.anyio
    async def test_settings_blocked_on_completed(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        # Manually set to completed
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'completed' WHERE id = ?", (sim_id,))
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={"platforms": ["twitter"]})
        assert resp.status_code == 409


class TestFrontendBackendContractPhase7b:
    @pytest.mark.anyio
    async def test_capabilities_response_has_frontend_required_fields(self, client):
        resp = await client.get("/api/capabilities")
        data = resp.json()["data"]
        assert "engines" in data
        assert "models" in data
        for m in data["models"]:
            assert "id" in m
            assert "label" in m
            assert "supports_thinking" in m

    @pytest.mark.anyio
    async def test_simulation_response_includes_model_fields(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim = resp.json()["data"]
        resp = await client.get(f"/api/simulations/{sim['id']}")
        d = resp.json()["data"]
        assert "prep_model" in d
        assert "run_model" in d
