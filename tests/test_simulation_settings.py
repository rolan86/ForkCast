"""Tests for AVAILABLE_MODELS constant and DB V3 migration."""

import sqlite3
from pathlib import Path

import pytest


class TestAvailableModels:
    def test_available_models_exists(self):
        from forkcast.config import AVAILABLE_MODELS

        assert AVAILABLE_MODELS is not None

    def test_available_models_is_list(self):
        from forkcast.config import AVAILABLE_MODELS

        assert isinstance(AVAILABLE_MODELS, list)
        assert len(AVAILABLE_MODELS) >= 2

    def test_each_model_has_required_fields(self):
        from forkcast.config import AVAILABLE_MODELS

        for model in AVAILABLE_MODELS:
            assert "id" in model, f"Model missing 'id': {model}"
            assert "label" in model, f"Model missing 'label': {model}"
            assert "supports_thinking" in model, f"Model missing 'supports_thinking': {model}"

    def test_supports_thinking_is_bool(self):
        from forkcast.config import AVAILABLE_MODELS

        for model in AVAILABLE_MODELS:
            assert isinstance(model["supports_thinking"], bool), (
                f"supports_thinking must be bool, got {type(model['supports_thinking'])} for {model['id']}"
            )

    def test_contains_haiku(self):
        from forkcast.config import AVAILABLE_MODELS

        ids = [m["id"] for m in AVAILABLE_MODELS]
        assert any("haiku" in mid.lower() for mid in ids), f"No haiku model found in {ids}"

    def test_contains_sonnet(self):
        from forkcast.config import AVAILABLE_MODELS

        ids = [m["id"] for m in AVAILABLE_MODELS]
        assert any("sonnet" in mid.lower() for mid in ids), f"No sonnet model found in {ids}"

    def test_haiku_does_not_support_thinking(self):
        from forkcast.config import AVAILABLE_MODELS

        haiku_models = [m for m in AVAILABLE_MODELS if "haiku" in m["id"].lower()]
        assert len(haiku_models) >= 1
        for m in haiku_models:
            assert m["supports_thinking"] is False, f"Haiku should not support thinking: {m}"

    def test_sonnet_supports_thinking(self):
        from forkcast.config import AVAILABLE_MODELS

        sonnet_models = [m for m in AVAILABLE_MODELS if "sonnet" in m["id"].lower()]
        assert len(sonnet_models) >= 1
        for m in sonnet_models:
            assert m["supports_thinking"] is True, f"Sonnet should support thinking: {m}"


class TestDBV3Migration:
    def test_schema_version_is_3(self):
        from forkcast.db.schema import SCHEMA_VERSION

        assert SCHEMA_VERSION == 3

    def test_fresh_db_has_prep_model_column(self, tmp_db_path):
        from forkcast.db.connection import get_db, init_db

        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "prep_model" in columns, f"prep_model not found in columns: {columns}"

    def test_fresh_db_has_run_model_column(self, tmp_db_path):
        from forkcast.db.connection import get_db, init_db

        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "run_model" in columns, f"run_model not found in columns: {columns}"

    def test_fresh_db_version_is_3(self, tmp_db_path):
        from forkcast.db.connection import init_db

        init_db(tmp_db_path)
        conn = sqlite3.connect(str(tmp_db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "3"

    def test_prep_model_is_nullable(self, tmp_db_path):
        """prep_model column should accept NULL (no default required)."""
        from forkcast.db.connection import get_db, init_db

        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("p1", "_default", "Test", "created", "Test requirement"),
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status) VALUES (?, ?, ?)",
                ("s1", "p1", "created"),
            )
        with get_db(tmp_db_path) as conn:
            row = conn.execute(
                "SELECT prep_model FROM simulations WHERE id = 's1'"
            ).fetchone()
            assert row is not None
            assert row["prep_model"] is None

    def test_run_model_is_nullable(self, tmp_db_path):
        """run_model column should accept NULL (no default required)."""
        from forkcast.db.connection import get_db, init_db

        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("p2", "_default", "Test2", "created", "Test requirement 2"),
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status) VALUES (?, ?, ?)",
                ("s2", "p2", "created"),
            )
        with get_db(tmp_db_path) as conn:
            row = conn.execute(
                "SELECT run_model FROM simulations WHERE id = 's2'"
            ).fetchone()
            assert row is not None
            assert row["run_model"] is None

    def test_v2_to_v3_migration_adds_prep_model(self, tmp_db_path):
        """V2 DB migrated to V3 should have prep_model column."""
        from forkcast.db.connection import get_db, init_db
        from forkcast.db.schema import TABLES_V2

        # Create a V2 database
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V2)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
        conn.commit()
        conn.close()

        # Run migration
        init_db(tmp_db_path)

        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "prep_model" in columns, f"prep_model not found after migration: {columns}"

    def test_v2_to_v3_migration_adds_run_model(self, tmp_db_path):
        """V2 DB migrated to V3 should have run_model column."""
        from forkcast.db.connection import get_db, init_db
        from forkcast.db.schema import TABLES_V2

        # Create a V2 database
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V2)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
        conn.commit()
        conn.close()

        # Run migration
        init_db(tmp_db_path)

        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "run_model" in columns, f"run_model not found after migration: {columns}"

    def test_v2_to_v3_migration_updates_version(self, tmp_db_path):
        """V2→V3 migration should update schema_version to 3."""
        from forkcast.db.connection import init_db
        from forkcast.db.schema import TABLES_V2

        # Create a V2 database
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V2)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
        conn.commit()
        conn.close()

        # Run migration
        init_db(tmp_db_path)

        conn = sqlite3.connect(str(tmp_db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        conn.close()
        assert row is not None
        assert row[0] == "3"

    def test_v2_to_v3_migration_preserves_existing_data(self, tmp_db_path):
        """V2→V3 migration should not lose existing simulation data."""
        from forkcast.db.connection import get_db, init_db
        from forkcast.db.schema import TABLES_V2

        # Create a V2 database with data
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V2)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '2')")
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'MyProj', 'created', 'req', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, platforms) "
            "VALUES ('s1', 'p1', 'completed', '[\"twitter\"]')"
        )
        conn.commit()
        conn.close()

        # Run migration
        init_db(tmp_db_path)

        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT status, platforms FROM simulations WHERE id = 's1'").fetchone()
            assert row is not None
            assert row["status"] == "completed"
            assert row["platforms"] == '["twitter"]'


import json
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


def _create_project(db_path):
    from forkcast.db.connection import get_db
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
        )


class TestPatchSettings:
    @pytest.mark.anyio
    async def test_patch_updates_engine(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={"engine_type": "claude"})
        assert resp.status_code == 200
        resp = await client.get(f"/api/simulations/{sim_id}")
        assert resp.json()["data"]["engine_type"] == "claude"

    @pytest.mark.anyio
    async def test_patch_updates_models(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "prep_model": "claude-haiku-4-5",
            "run_model": "claude-sonnet-4-6",
        })
        assert resp.status_code == 200
        resp = await client.get(f"/api/simulations/{sim_id}")
        assert resp.json()["data"]["prep_model"] == "claude-haiku-4-5"

    @pytest.mark.anyio
    async def test_patch_rejects_completed_simulation(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        from forkcast.db.connection import get_db
        with get_db(tmp_db_path) as conn:
            conn.execute("UPDATE simulations SET status = 'completed' WHERE id = ?", (sim_id,))
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={"engine_type": "claude"})
        assert resp.status_code == 409

    @pytest.mark.anyio
    async def test_patch_partial_update(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={"platforms": ["twitter"]})
        assert resp.status_code == 200
        resp = await client.get(f"/api/simulations/{sim_id}")
        assert resp.json()["data"]["platforms"] == ["twitter"]


class TestSmartEngineDefaults:
    @pytest.mark.anyio
    async def test_create_reads_engine_from_domain(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        data = resp.json()["data"]
        # _default domain manifest has sim_engine: claude
        assert data["engine_type"] == "claude"
