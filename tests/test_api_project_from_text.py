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
async def test_create_project_from_text(app, tmp_data_dir):
    """POST /api/projects/from-text creates project with inline documents."""
    payload = {
        "domain": "_default",
        "requirement": "How would stakeholders react to WidgetX?",
        "name": "WidgetX",
        "documents": [
            {"filename": "overview.txt", "content": "WidgetX is a new product."},
            {"filename": "landscape.txt", "content": "Market analysis content."},
        ],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    data = body["data"]
    assert data["id"].startswith("proj_")
    assert data["name"] == "WidgetX"
    assert data["domain"] == "_default"
    assert data["status"] == "created"
    assert data["requirement"] == "How would stakeholders react to WidgetX?"
    assert len(data["files"]) == 2
    assert data["files"][0]["filename"] == "overview.txt"
    assert data["files"][0]["size"] == len("WidgetX is a new product.")

    # Verify files written to disk
    project_dir = tmp_data_dir / data["id"] / "uploads"
    assert (project_dir / "overview.txt").read_text() == "WidgetX is a new product."
    assert (project_dir / "landscape.txt").read_text() == "Market analysis content."


@pytest.mark.asyncio
async def test_create_project_from_text_default_name(app):
    """Name defaults to 'Project <suffix>' when omitted."""
    payload = {
        "domain": "_default",
        "requirement": "Test question",
        "documents": [{"filename": "doc.txt", "content": "Content here."}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 201
    assert resp.json()["data"]["name"].startswith("Project ")


@pytest.mark.asyncio
async def test_create_project_from_text_missing_documents(app):
    """Should return 400 when documents list is missing."""
    payload = {"domain": "_default", "requirement": "Test question"}
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_project_from_text_empty_documents(app):
    """Should return 400 when documents list is empty."""
    payload = {
        "domain": "_default",
        "requirement": "Test question",
        "documents": [],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_project_from_text_empty_content(app):
    """Should return 400 when a document has empty content."""
    payload = {
        "domain": "_default",
        "requirement": "Test question",
        "documents": [{"filename": "empty.txt", "content": ""}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_project_from_text_empty_filename(app):
    """Should return 400 when a document has empty filename."""
    payload = {
        "domain": "_default",
        "requirement": "Test question",
        "documents": [{"filename": "", "content": "Some content"}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_project_from_text_invalid_domain(app):
    """Should return 400 when domain doesn't exist."""
    payload = {
        "domain": "nonexistent_domain",
        "requirement": "Test question",
        "documents": [{"filename": "doc.txt", "content": "Content."}],
    }
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post("/api/projects/from-text", json=payload)

    assert resp.status_code == 400
    assert "domain" in resp.json()["error"].lower()
