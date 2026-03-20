import json
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    from forkcast.api.app import create_app
    return create_app()


def _create_project(tmp_data_dir, tmp_db_path):
    """Helper to create a project with files for graph building."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)
    project_id = "proj_graph_test"
    uploads = tmp_data_dir / project_id / "uploads"
    uploads.mkdir(parents=True)
    (uploads / "doc.txt").write_text("Alice works at TechCorp researching AI.")

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Graph Test', 'created', 'What will happen?', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO project_files (project_id, filename, path, size, created_at) "
            "VALUES (?, 'doc.txt', ?, 40, datetime('now'))",
            (project_id, str(uploads / "doc.txt")),
        )
    return project_id


def _mock_pipeline_result():
    return {
        "status": "complete",
        "graph_id": "graph_abc123",
        "node_count": 3,
        "edge_count": 2,
        "entities_extracted": 3,
        "chunks_processed": 1,
    }


@pytest.mark.asyncio
async def test_build_graph_triggers(app, tmp_data_dir, tmp_db_path):
    """POST /api/projects/{id}/build-graph should trigger graph building."""
    project_id = _create_project(tmp_data_dir, tmp_db_path)

    with patch("forkcast.api.graph_routes.build_graph_pipeline", return_value=_mock_pipeline_result()):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(f"/api/projects/{project_id}/build-graph")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["graph_id"] == "graph_abc123"


@pytest.mark.asyncio
async def test_build_graph_project_not_found(app):
    """POST /api/projects/{id}/build-graph with bad ID should 404."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/projects/proj_nonexistent/build-graph")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_graph_for_project(app, tmp_data_dir, tmp_db_path):
    """GET /api/projects/{id}/graph should return graph metadata."""
    from forkcast.db.connection import get_db

    project_id = _create_project(tmp_data_dir, tmp_db_path)

    def _pipeline_with_db_insert(**kwargs):
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
                "VALUES ('graph_abc123', ?, 'complete', 3, 2, 'graph.json', datetime('now'))",
                (project_id,),
            )
        return _mock_pipeline_result()

    with patch("forkcast.api.graph_routes.build_graph_pipeline", side_effect=_pipeline_with_db_insert):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post(f"/api/projects/{project_id}/build-graph")
            resp = await client.get(f"/api/projects/{project_id}/graph")

    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
