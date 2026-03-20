import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


@pytest.mark.asyncio
async def test_list_domains(app, tmp_domains_dir):
    """GET /api/domains should return available domains."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/domains")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    domains = body["data"]
    assert isinstance(domains, list)
    assert any(d["name"] == "_default" for d in domains)


@pytest.mark.asyncio
async def test_create_domain(app, tmp_domains_dir):
    """POST /api/domains should scaffold a new domain."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/domains",
            json={
                "name": "test-domain",
                "description": "A test domain",
                "language": "en",
                "sim_engine": "claude",
                "platforms": ["reddit"],
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["name"] == "test-domain"

    # Verify domain is now loadable
    assert (tmp_domains_dir / "test-domain" / "manifest.yaml").exists()


@pytest.mark.asyncio
async def test_create_duplicate_domain(app, tmp_domains_dir):
    """POST /api/domains with existing name should fail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create first
        await client.post(
            "/api/domains",
            json={"name": "dup", "description": "First", "language": "en", "sim_engine": "oasis", "platforms": ["twitter"]},
        )
        # Duplicate
        resp = await client.post(
            "/api/domains",
            json={"name": "dup", "description": "Second", "language": "en", "sim_engine": "oasis", "platforms": ["twitter"]},
        )

    assert resp.status_code == 409
    assert resp.json()["success"] is False
