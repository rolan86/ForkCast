"""End-to-end tests for Phase 7a: Backend + Frontend integration.

Tests the full pipeline from project creation through simulation,
verifying that:
- Backend API endpoints chain correctly (project → graph → simulation)
- Frontend build output is valid
- CORS headers are set correctly for frontend origin
- SSE streaming endpoints respond with correct content-type
- The graph/data endpoint returns D3-compatible format
- API response envelope is consistent across all endpoints
"""

import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.db.connection import get_db, init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def app(tmp_data_dir, tmp_domains_dir, monkeypatch):
    """Create a fully configured app instance with isolated DB and domains."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings

    reset_settings()
    settings = __import__("forkcast.config", fromlist=["get_settings"]).get_settings()
    init_db(settings.db_path)

    from forkcast.api.app import create_app

    return create_app()


@pytest.fixture
def client(app):
    """Async HTTP client connected to the test app."""
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_project(client):
    """Create a project via API, return its ID."""
    resp = await client.post(
        "/api/projects",
        data={"domain": "_default", "requirement": "Will AI regulation increase?"},
        files={"files": ("report.txt", io.BytesIO(b"EU AI Act analysis document with many details about regulation."), "text/plain")},
    )
    assert resp.status_code == 201, f"Project creation failed: {resp.text}"
    data = resp.json()
    assert data["success"] is True
    return data["data"]


def _seed_graph(db_path, data_dir, project_id):
    """Insert a built graph into the DB and write a graph.json file."""
    graph_id = f"graph_{project_id}"
    graph_dir = data_dir / project_id
    graph_dir.mkdir(parents=True, exist_ok=True)
    graph_path = graph_dir / "graph.json"

    graph_data = {
        "directed": True,
        "multigraph": False,
        "graph": {},
        "nodes": [
            {"id": "EU AI Act", "type": "Concept", "description": "European regulation on artificial intelligence"},
            {"id": "Google", "type": "Organization", "description": "Technology company"},
            {"id": "OpenAI", "type": "Organization", "description": "AI research lab"},
            {"id": "Compliance", "type": "Concept", "description": "Regulatory compliance"},
        ],
        "links": [
            {"source": "Google", "target": "EU AI Act", "label": "subject_to"},
            {"source": "OpenAI", "target": "EU AI Act", "label": "subject_to"},
            {"source": "EU AI Act", "target": "Compliance", "label": "requires"},
        ],
    }
    graph_path.write_text(json.dumps(graph_data))

    with get_db(db_path) as conn:
        conn.execute(
            "UPDATE projects SET status = 'graph_built' WHERE id = ?",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path, created_at) "
            "VALUES (?, ?, 'built', 4, 3, ?, datetime('now'))",
            (graph_id, project_id, str(graph_path)),
        )

    return graph_id


# ---------------------------------------------------------------------------
# 1. Full Pipeline E2E Test
# ---------------------------------------------------------------------------


class TestFullPipelineE2E:
    """Test the complete project → graph → simulation pipeline via API."""

    @pytest.mark.asyncio
    async def test_project_creation_and_listing(self, app, client):
        """Create a project, verify it appears in the project list."""
        async with client:
            project = await _create_project(client)
            assert project["id"].startswith("proj_")
            assert project["status"] == "created"
            assert project["domain"] == "_default"
            assert len(project["files"]) == 1
            assert project["files"][0]["filename"] == "report.txt"

            # List should contain it
            list_resp = await client.get("/api/projects")
            assert list_resp.status_code == 200
            projects = list_resp.json()["data"]
            assert any(p["id"] == project["id"] for p in projects)

            # Get by ID
            get_resp = await client.get(f"/api/projects/{project['id']}")
            assert get_resp.status_code == 200
            assert get_resp.json()["data"]["id"] == project["id"]

    @pytest.mark.asyncio
    async def test_graph_build_and_data_endpoint(self, app, client, tmp_data_dir, tmp_db_path):
        """Build a graph, then verify the D3 data endpoint returns correct format."""
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            project_id = project["id"]

            # Seed a pre-built graph (mocking the pipeline)
            _seed_graph(settings.db_path, settings.data_dir, project_id)

            # GET /graph should return metadata
            graph_resp = await client.get(f"/api/projects/{project_id}/graph")
            assert graph_resp.status_code == 200
            graph_meta = graph_resp.json()["data"]
            assert graph_meta["status"] == "built"
            assert graph_meta["node_count"] == 4
            assert graph_meta["edge_count"] == 3

            # GET /graph/data should return D3-friendly format
            data_resp = await client.get(f"/api/projects/{project_id}/graph/data")
            assert data_resp.status_code == 200
            d3_data = data_resp.json()["data"]

            assert len(d3_data["nodes"]) == 4
            assert len(d3_data["edges"]) == 3

            # Verify node structure
            node_ids = {n["id"] for n in d3_data["nodes"]}
            assert "EU AI Act" in node_ids
            assert "Google" in node_ids

            # Verify edge structure
            edge = d3_data["edges"][0]
            assert "source" in edge
            assert "target" in edge
            assert "label" in edge

    @pytest.mark.asyncio
    async def test_simulation_lifecycle(self, app, client, tmp_data_dir, tmp_db_path):
        """Create project → seed graph → create simulation → prepare → list."""
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            project_id = project["id"]
            _seed_graph(settings.db_path, settings.data_dir, project_id)

            # Create simulation
            sim_resp = await client.post("/api/simulations", json={
                "project_id": project_id,
                "engine_type": "oasis",
                "platforms": ["twitter", "reddit"],
            })
            assert sim_resp.status_code == 201
            sim = sim_resp.json()["data"]
            assert sim["status"] == "created"
            assert sim["project_id"] == project_id
            sim_id = sim["id"]

            # Get simulation
            get_resp = await client.get(f"/api/simulations/{sim_id}")
            assert get_resp.status_code == 200
            assert get_resp.json()["data"]["id"] == sim_id

            # List simulations
            list_resp = await client.get("/api/simulations")
            assert list_resp.status_code == 200
            sims = list_resp.json()["data"]
            assert any(s["id"] == sim_id for s in sims)

            # Trigger prepare (mocked)
            with patch("forkcast.api.simulation_routes.ClaudeClient"):
                with patch("forkcast.api.simulation_routes.prepare_simulation"):
                    prep_resp = await client.post(f"/api/simulations/{sim_id}/prepare")

            assert prep_resp.status_code == 200
            assert prep_resp.json()["data"]["status"] == "preparing"

    @pytest.mark.asyncio
    async def test_graph_data_404_without_graph(self, app, client):
        """Graph/data should 404 when no graph exists for project."""
        async with client:
            project = await _create_project(client)
            resp = await client.get(f"/api/projects/{project['id']}/graph/data")
            assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 2. CORS Configuration Tests
# ---------------------------------------------------------------------------


class TestCORSConfiguration:
    """Verify CORS headers are set correctly for the frontend."""

    @pytest.mark.asyncio
    async def test_cors_allows_frontend_origin(self, app, client):
        """OPTIONS preflight from frontend origin should succeed."""
        async with client:
            resp = await client.options(
                "/api/projects",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "Content-Type",
                },
            )
            assert resp.status_code == 200
            assert "http://localhost:5173" in resp.headers.get("access-control-allow-origin", "")

    @pytest.mark.asyncio
    async def test_cors_headers_on_get(self, app, client):
        """Regular GET from frontend origin should include CORS headers."""
        async with client:
            resp = await client.get(
                "/health",
                headers={"Origin": "http://localhost:5173"},
            )
            assert resp.status_code == 200
            assert "http://localhost:5173" in resp.headers.get("access-control-allow-origin", "")


# ---------------------------------------------------------------------------
# 3. API Response Envelope Consistency
# ---------------------------------------------------------------------------


class TestAPIEnvelopeConsistency:
    """All API responses should follow the {success, data/error} envelope."""

    @pytest.mark.asyncio
    async def test_success_envelope(self, app, client):
        async with client:
            resp = await client.get("/health")
            body = resp.json()
            assert "success" in body
            assert body["success"] is True
            assert "data" in body

    @pytest.mark.asyncio
    async def test_error_envelope_404(self, app, client):
        async with client:
            resp = await client.get("/api/projects/nonexistent")
            body = resp.json()
            assert body["success"] is False
            assert "error" in body

    @pytest.mark.asyncio
    async def test_domains_endpoint(self, app, client):
        """GET /api/domains should list available domains."""
        async with client:
            resp = await client.get("/api/domains")
            assert resp.status_code == 200
            body = resp.json()
            assert body["success"] is True
            assert isinstance(body["data"], list)
            # Should include _default domain from fixture
            names = [d["name"] for d in body["data"]]
            assert "_default" in names


# ---------------------------------------------------------------------------
# 4. SSE Streaming Endpoint Tests
# ---------------------------------------------------------------------------


class TestSSEEndpoints:
    """Verify SSE streaming endpoints respond with correct content-type."""

    @pytest.mark.asyncio
    async def test_graph_build_stream_content_type(self, app, client, tmp_data_dir, tmp_db_path):
        """GET /build-graph/stream should return text/event-stream."""
        from forkcast.api.graph_routes import _progress_queues

        async with client:
            project = await _create_project(client)
            project_id = project["id"]

            # Pre-populate the queue with a sentinel so the stream closes immediately
            _progress_queues[project_id].put_nowait(None)

            resp = await client.get(
                f"/api/projects/{project_id}/build-graph/stream",
                headers={"Accept": "text/event-stream"},
            )
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")

    @pytest.mark.asyncio
    async def test_simulation_prepare_stream_content_type(self, app, client, tmp_data_dir, tmp_db_path):
        """GET /simulations/{id}/prepare/stream should return text/event-stream."""
        import asyncio as _asyncio

        from forkcast.api.simulation_routes import _prepare_queues
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            project_id = project["id"]
            _seed_graph(settings.db_path, settings.data_dir, project_id)

            # Create simulation
            sim_resp = await client.post("/api/simulations", json={"project_id": project_id})
            sim_id = sim_resp.json()["data"]["id"]

            # Pre-create a queue with a sentinel so the stream closes immediately
            q = _asyncio.Queue()
            q.put_nowait(None)
            _prepare_queues[sim_id] = q

            resp = await client.get(
                f"/api/simulations/{sim_id}/prepare/stream",
                headers={"Accept": "text/event-stream"},
            )
            assert resp.status_code == 200
            assert resp.headers.get("content-type", "").startswith("text/event-stream")


# ---------------------------------------------------------------------------
# 5. Frontend Build Validation
# ---------------------------------------------------------------------------


class TestFrontendBuild:
    """Verify the frontend build output is valid and complete."""

    def test_dist_index_html_exists(self):
        """Frontend build should produce an index.html."""
        dist = Path(__file__).parent.parent / "frontend" / "dist"
        index = dist / "index.html"
        assert index.exists(), f"frontend/dist/index.html not found — run 'npm run build' first"

    def test_dist_index_html_references_assets(self):
        """index.html should reference bundled JS and CSS assets."""
        dist = Path(__file__).parent.parent / "frontend" / "dist"
        html = (dist / "index.html").read_text()
        assert "/assets/" in html, "index.html should reference /assets/ for bundled files"
        assert ".js" in html, "index.html should include a JS bundle reference"

    def test_dist_has_js_bundles(self):
        """Build should produce JavaScript bundles."""
        assets = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        assert assets.exists(), "frontend/dist/assets/ not found"
        js_files = list(assets.glob("*.js"))
        assert len(js_files) >= 1, f"Expected JS bundles, found: {js_files}"

    def test_dist_has_css_bundle(self):
        """Build should produce a CSS bundle (Tailwind output)."""
        assets = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        css_files = list(assets.glob("*.css"))
        assert len(css_files) >= 1, f"Expected CSS bundle, found: {css_files}"

    def test_dist_vue_router_routes_in_bundle(self):
        """Bundled JS should contain Vue Router route paths."""
        assets = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        # Find the main entry bundle (not a lazy chunk)
        js_files = list(assets.glob("index-*.js"))
        assert js_files, "No index JS bundle found"
        content = js_files[0].read_text()
        assert "/projects" in content, "Router should include /projects route"

    def test_dist_lazy_chunks_exist(self):
        """Lazy-loaded view chunks should exist (code splitting)."""
        assets = Path(__file__).parent.parent / "frontend" / "dist" / "assets"
        js_files = list(assets.glob("*.js"))
        # We expect at least: index + GraphTab (D3) + a projects chunk
        assert len(js_files) >= 2, f"Expected lazy chunks, found {len(js_files)} JS files"


# ---------------------------------------------------------------------------
# 6. Frontend-Backend Contract Tests
# ---------------------------------------------------------------------------


class TestFrontendBackendContract:
    """Verify the API contract the frontend depends on."""

    @pytest.mark.asyncio
    async def test_project_response_has_frontend_required_fields(self, app, client):
        """Frontend ProjectListView needs: id, name, status, domain, requirement, created_at, files."""
        async with client:
            project = await _create_project(client)
            resp = await client.get(f"/api/projects/{project['id']}")
            data = resp.json()["data"]

            required = ["id", "name", "status", "domain", "requirement", "created_at", "files"]
            for field in required:
                assert field in data, f"Missing field '{field}' required by frontend ProjectListView"

    @pytest.mark.asyncio
    async def test_graph_data_response_has_d3_fields(self, app, client, tmp_data_dir, tmp_db_path):
        """Frontend GraphTab needs: nodes[{id, type, description}], edges[{source, target, label}]."""
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            _seed_graph(settings.db_path, settings.data_dir, project["id"])

            resp = await client.get(f"/api/projects/{project['id']}/graph/data")
            d3 = resp.json()["data"]

            assert "nodes" in d3
            assert "edges" in d3
            assert len(d3["nodes"]) > 0

            node = d3["nodes"][0]
            for field in ["id", "type", "description"]:
                assert field in node, f"Node missing '{field}' required by D3 renderer"

            edge = d3["edges"][0]
            for field in ["source", "target", "label"]:
                assert field in edge, f"Edge missing '{field}' required by D3 renderer"

    @pytest.mark.asyncio
    async def test_simulation_response_has_frontend_required_fields(self, app, client, tmp_data_dir, tmp_db_path):
        """Frontend SimulationTab needs: id, project_id, status, engine_type, platforms, created_at."""
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            _seed_graph(settings.db_path, settings.data_dir, project["id"])

            sim_resp = await client.post("/api/simulations", json={"project_id": project["id"]})
            sim = sim_resp.json()["data"]

            required = ["id", "project_id", "status", "engine_type", "platforms"]
            for field in required:
                assert field in sim, f"Missing field '{field}' required by frontend SimulationTab"

    @pytest.mark.asyncio
    async def test_graph_metadata_has_frontend_required_fields(self, app, client, tmp_data_dir, tmp_db_path):
        """Frontend OverviewTab needs: status, node_count, edge_count from graph metadata."""
        from forkcast.config import get_settings

        settings = get_settings()

        async with client:
            project = await _create_project(client)
            _seed_graph(settings.db_path, settings.data_dir, project["id"])

            resp = await client.get(f"/api/projects/{project['id']}/graph")
            graph = resp.json()["data"]

            for field in ["status", "node_count", "edge_count"]:
                assert field in graph, f"Missing field '{field}' required by frontend OverviewTab"

    @pytest.mark.asyncio
    async def test_domains_response_has_frontend_required_fields(self, app, client):
        """Frontend ProjectWizard needs: domains list with name field."""
        async with client:
            resp = await client.get("/api/domains")
            domains = resp.json()["data"]
            assert len(domains) >= 1
            assert "name" in domains[0], "Domain missing 'name' field required by ProjectWizard"
