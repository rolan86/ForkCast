"""API tests for dynamics settings and capabilities."""

import pytest
from fastapi.testclient import TestClient

from forkcast.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


class TestCapabilitiesIntegrators:
    """Verify capabilities endpoint includes integrator info."""

    def test_capabilities_includes_integrators(self, client):
        resp = client.get("/api/capabilities")
        data = resp.json()
        assert "integrators" in data.get("data", {})
        methods = data["data"]["integrators"]["methods"]
        ids = [m["id"] for m in methods]
        assert "euler" in ids
        assert "rk" in ids
        assert "adaptive" in ids

    def test_integrator_descriptions_present(self, client):
        resp = client.get("/api/capabilities")
        methods = resp.json()["data"]["integrators"]["methods"]
        for m in methods:
            assert "description" in m
            assert len(m["description"]) > 10

    def test_rk_has_order_param(self, client):
        resp = client.get("/api/capabilities")
        methods = resp.json()["data"]["integrators"]["methods"]
        rk = next(m for m in methods if m["id"] == "rk")
        assert "order" in rk["params"]

    def test_adaptive_has_tolerance_and_max_order(self, client):
        resp = client.get("/api/capabilities")
        methods = resp.json()["data"]["integrators"]["methods"]
        adaptive = next(m for m in methods if m["id"] == "adaptive")
        assert "tolerance" in adaptive["params"]
        assert "max_order" in adaptive["params"]
