import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    """Create a test FastAPI app."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_health_endpoint(app):
    """GET /health should return ok status."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["data"]["service"] == "ForkCast"


@pytest.mark.asyncio
async def test_not_found_returns_json(app):
    """Unknown routes should return JSON error, not HTML."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/nonexistent")

    assert resp.status_code == 404
