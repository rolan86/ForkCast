"""Tests for report and chat API routes."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.db.connection import get_db, init_db


@pytest.fixture
def app(tmp_data_dir, tmp_db_path, tmp_domains_dir, monkeypatch):
    """Create app with initialized DB."""
    monkeypatch.setenv("FORKCAST_DATA_DIR", str(tmp_data_dir))
    monkeypatch.setenv("FORKCAST_DOMAINS_DIR", str(tmp_domains_dir))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    from forkcast.config import reset_settings
    reset_settings()

    init_db(tmp_db_path)

    from forkcast.api.app import create_app
    return create_app()


def _insert_project_sim(db_path: Path, project_id: str = "proj_test1", sim_id: str = "sim_test1"):
    """Insert a minimal project and simulation row."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, '_default', 'Test', 'graph_built', 'Predict something', datetime('now'))",
            (project_id,),
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, engine_type, platforms, created_at) "
            "VALUES (?, ?, 'completed', 'oasis', '[\"twitter\"]', datetime('now'))",
            (sim_id, project_id),
        )
    return project_id, sim_id


def _insert_report(db_path: Path, sim_id: str, report_id: str = "report_test1", status: str = "completed", content: str = "# Report\n\nHello."):
    """Insert a minimal report row."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO reports (id, simulation_id, status, content_markdown, created_at) "
            "VALUES (?, ?, ?, ?, datetime('now'))",
            (report_id, sim_id, status, content),
        )
    return report_id


# ---------------------------------------------------------------------------
# Report endpoints
# ---------------------------------------------------------------------------

class TestListReports:
    @pytest.mark.asyncio
    async def test_list_reports_empty(self, app):
        """GET /api/reports returns empty list when no reports exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == []

    @pytest.mark.asyncio
    async def test_list_reports_filter(self, app, tmp_db_path):
        """GET /api/reports?simulation_id=x filters correctly."""
        _insert_project_sim(tmp_db_path, "proj_a", "sim_a")
        _insert_project_sim(tmp_db_path, "proj_b", "sim_b")
        _insert_report(tmp_db_path, "sim_a", "report_a1")
        _insert_report(tmp_db_path, "sim_a", "report_a2")
        _insert_report(tmp_db_path, "sim_b", "report_b1")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports?simulation_id=sim_a")

        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data) == 2
        assert all(r["simulation_id"] == "sim_a" for r in data)


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_generate_simulation_not_found(self, app):
        """POST /api/reports/generate returns 404 when simulation doesn't exist."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post(
                "/api/reports/generate",
                json={"simulation_id": "nonexistent"},
            )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_generate_returns_report_id(self, app, tmp_db_path):
        """POST /api/reports/generate starts background task and returns report_id."""
        _insert_project_sim(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.report_routes.create_llm_client"):
                with patch("forkcast.api.report_routes.generate_report") as mock_gen:
                    mock_gen.return_value = MagicMock(
                        report_id="report_generated",
                        simulation_id="sim_test1",
                        tool_rounds=2,
                        tokens_used={"input": 100, "output": 50},
                    )
                    response = await client.post(
                        "/api/reports/generate",
                        json={"simulation_id": "sim_test1"},
                    )

        assert response.status_code == 200
        data = response.json()["data"]
        assert "report_id" in data
        assert data["status"] == "generating"


class TestGetReport:
    @pytest.mark.asyncio
    async def test_get_report_not_found(self, app):
        """GET /api/reports/nonexistent returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/nonexistent")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_report(self, app, tmp_db_path):
        """Create a report in DB, GET /api/reports/{id} returns it."""
        _insert_project_sim(tmp_db_path)
        _insert_report(tmp_db_path, "sim_test1", "report_test1")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/report_test1")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["id"] == "report_test1"
        assert data["simulation_id"] == "sim_test1"
        assert data["status"] == "completed"
        assert "# Report" in (data.get("content_markdown") or "")


class TestExportReport:
    @pytest.mark.asyncio
    async def test_export_not_found(self, app):
        """GET /api/reports/nonexistent/export returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/nonexistent/export")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_export_markdown(self, app, tmp_db_path):
        """Create a report, GET /api/reports/{id}/export returns text/markdown content type."""
        _insert_project_sim(tmp_db_path)
        _insert_report(tmp_db_path, "sim_test1", "report_export1", content="# My Report\n\nContent here.")

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/api/reports/report_export1/export")

        assert response.status_code == 200
        assert "text/markdown" in response.headers.get("content-type", "")
        assert "# My Report" in response.text


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

class TestChatReport:
    @pytest.mark.asyncio
    async def test_chat_report_not_found(self, app):
        """POST /api/chat/report with bad report_id returns error event in SSE stream."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.report_routes.create_llm_client"):
                response = await client.post(
                    "/api/chat/report",
                    json={"report_id": "nonexistent_report", "message": "Hello"},
                )

        assert response.status_code == 200
        # SSE stream should contain an error event
        assert "error" in response.text

    @pytest.mark.asyncio
    async def test_chat_report_valid(self, app, tmp_db_path):
        """POST /api/chat/report with valid report returns 200."""
        from forkcast.report.models import StreamEvent

        _insert_project_sim(tmp_db_path)
        _insert_report(tmp_db_path, "sim_test1", "report_chat1")

        mock_events = [
            StreamEvent(type="text_delta", data="Hello from report"),
            StreamEvent(type="done", data={"stop_reason": "end_turn"}),
        ]

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.report_routes.create_llm_client"):
                with patch("forkcast.api.report_routes.report_chat", return_value=iter(mock_events)):
                    response = await client.post(
                        "/api/chat/report",
                        json={"report_id": "report_chat1", "message": "What happened?"},
                    )

        assert response.status_code == 200


class TestChatAgent:
    @pytest.mark.asyncio
    async def test_chat_agent_not_found(self, app, tmp_db_path):
        """POST /api/chat/agent with bad agent/sim returns error event in SSE stream."""
        _insert_project_sim(tmp_db_path)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.report_routes.create_llm_client"):
                response = await client.post(
                    "/api/chat/agent",
                    json={
                        "simulation_id": "sim_test1",
                        "agent_id": 9999,
                        "message": "Hello",
                    },
                )

        assert response.status_code == 200
        # SSE stream should contain an error event (agent not found)
        assert "error" in response.text

    @pytest.mark.asyncio
    async def test_chat_agent_sim_not_found(self, app):
        """POST /api/chat/agent with nonexistent sim returns 404."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with patch("forkcast.api.report_routes.create_llm_client"):
                response = await client.post(
                    "/api/chat/agent",
                    json={
                        "simulation_id": "nonexistent_sim",
                        "agent_id": 1,
                        "message": "Hello",
                    },
                )

        assert response.status_code == 404
