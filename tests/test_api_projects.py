import io

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
async def test_create_project(app):
    """POST /api/projects should create a project with uploaded files."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/projects",
            data={"domain": "_default", "requirement": "What will happen next?"},
            files={"files": ("test.txt", io.BytesIO(b"Some document content"), "text/plain")},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"].startswith("proj_")
    assert body["data"]["status"] == "created"
    assert body["data"]["domain"] == "_default"
    assert len(body["data"]["files"]) == 1


@pytest.mark.asyncio
async def test_create_project_missing_requirement(app):
    """POST /api/projects without requirement should fail."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/api/projects",
            data={"domain": "_default"},
            files={"files": ("test.txt", io.BytesIO(b"content"), "text/plain")},
        )

    assert resp.status_code == 422  # FastAPI validation error


@pytest.mark.asyncio
async def test_get_project(app):
    """GET /api/projects/{id} should return project details."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create
        create_resp = await client.post(
            "/api/projects",
            data={"domain": "_default", "requirement": "Test question"},
            files={"files": ("doc.txt", io.BytesIO(b"Document text"), "text/plain")},
        )
        project_id = create_resp.json()["data"]["id"]

        # Get
        resp = await client.get(f"/api/projects/{project_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["id"] == project_id
    assert body["data"]["requirement"] == "Test question"


@pytest.mark.asyncio
async def test_get_project_not_found(app):
    """GET /api/projects/{id} with invalid ID should return 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/projects/proj_nonexistent")

    assert resp.status_code == 404
    assert resp.json()["success"] is False


@pytest.mark.asyncio
async def test_list_projects(app):
    """GET /api/projects should list all projects."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Create two projects
        for i in range(2):
            await client.post(
                "/api/projects",
                data={"domain": "_default", "requirement": f"Question {i}"},
                files={"files": (f"doc{i}.txt", io.BytesIO(f"Content {i}".encode()), "text/plain")},
            )

        resp = await client.get("/api/projects")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert len(body["data"]) >= 2
