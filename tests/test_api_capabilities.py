"""Tests for GET /api/capabilities endpoint."""
import pytest
from httpx import ASGITransport, AsyncClient
from forkcast.api.app import create_app


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


class TestCapabilitiesEndpoint:
    @pytest.mark.asyncio
    async def test_returns_engines_and_models(self, client):
        resp = await client.get("/api/capabilities")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "engines" in data
        assert "models" in data
        assert "claude" in data["engines"]
        assert data["engines"]["claude"]["available"] is True

    @pytest.mark.asyncio
    async def test_models_match_available_models(self, client):
        from forkcast.config import AVAILABLE_MODELS
        resp = await client.get("/api/capabilities")
        models = resp.json()["data"]["models"]
        assert len(models) == len(AVAILABLE_MODELS)
        for m in models:
            assert "id" in m
            assert "label" in m
            assert "supports_thinking" in m

    @pytest.mark.asyncio
    async def test_oasis_engine_reports_availability(self, client):
        resp = await client.get("/api/capabilities")
        oasis = resp.json()["data"]["engines"]["oasis"]
        assert "available" in oasis
        if not oasis["available"]:
            assert "reason" in oasis
