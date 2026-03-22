"""Tests for GET /api/projects/{id}/graph/data endpoint."""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_path / "data"))
    app = create_app()
    return app


@pytest.fixture
def setup_project_with_graph(app, tmp_path):
    """Insert a project and graph row, write a graph.json file."""
    from forkcast.config import get_settings
    settings = get_settings()
    init_db(settings.db_path)

    project_id = "proj_test1"
    graph_id = "graph_test1"
    graph_dir = settings.data_dir / project_id
    graph_dir.mkdir(parents=True)
    graph_path = graph_dir / "graph.json"

    # Write a minimal NetworkX node-link JSON
    graph_data = {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "AI Act", "type": "Concept", "description": "EU regulation"},
            {"id": "Google", "type": "Organization", "description": "Tech company"},
        ],
        "links": [
            {"source": "Google", "target": "AI Act", "label": "subject_to"},
        ],
    }
    graph_path.write_text(json.dumps(graph_data))

    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'req', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'built', 2, 1, ?, datetime('now'))",
            (graph_id, project_id, str(graph_path)),
        )

    return project_id


@pytest.mark.asyncio
async def test_get_graph_data_returns_d3_format(app, setup_project_with_graph):
    project_id = setup_project_with_graph
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"/api/projects/{project_id}/graph/data")
    assert resp.status_code == 200
    body = resp.json()["data"]
    assert len(body["nodes"]) == 2
    assert len(body["edges"]) == 1
    assert body["nodes"][0]["id"] == "AI Act"
    assert body["edges"][0]["label"] == "subject_to"


@pytest.mark.asyncio
async def test_get_graph_data_404_no_graph(app, tmp_path, monkeypatch):
    from forkcast.config import get_settings
    settings = get_settings()
    init_db(settings.db_path)
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('proj_nograph', '_default', 'Test', 'created', 'req', datetime('now'))"
        )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/projects/proj_nograph/graph/data")
    assert resp.status_code == 404
