"""Tests for simulation timing controls — schema, API, and config generator."""

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from forkcast.api.app import create_app
from forkcast.db.connection import get_db, init_db
from forkcast.db.schema import SCHEMA_VERSION
from forkcast.llm.client import LLMResponse
from forkcast.simulation.config_generator import generate_config
from forkcast.simulation.models import AgentProfile


class TestSchemaV5:
    def test_schema_version_is_6(self):
        assert SCHEMA_VERSION == 6

    def test_fresh_db_has_total_hours_column(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "total_hours" in columns

    def test_fresh_db_has_minutes_per_round_column(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "minutes_per_round" in columns

    def test_total_hours_is_nullable(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status) VALUES ('s1', 'p1', 'created')"
            )
        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT total_hours FROM simulations WHERE id = 's1'").fetchone()
            assert row["total_hours"] is None

    def test_minutes_per_round_is_nullable(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, status) VALUES ('s1', 'p1', 'created')"
            )
        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT minutes_per_round FROM simulations WHERE id = 's1'").fetchone()
            assert row["minutes_per_round"] is None

    def test_v4_to_v5_migration(self, tmp_db_path):
        from forkcast.db.schema import TABLES_V4
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V4)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '4')")
        conn.commit()
        conn.close()

        init_db(tmp_db_path)

        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(simulations)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "total_hours" in columns
            assert "minutes_per_round" in columns

    def test_v4_to_v5_migration_updates_version(self, tmp_db_path):
        from forkcast.db.schema import TABLES_V4
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V4)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '4')")
        conn.commit()
        conn.close()

        init_db(tmp_db_path)

        conn = sqlite3.connect(str(tmp_db_path))
        row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
        conn.close()
        assert row[0] == str(SCHEMA_VERSION)

    def test_v4_to_v5_migration_preserves_data(self, tmp_db_path):
        from forkcast.db.schema import TABLES_V4
        conn = sqlite3.connect(str(tmp_db_path))
        conn.executescript(TABLES_V4)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '4')")
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'MyProj', 'created', 'req', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id, status, engine_type, agent_mode) "
            "VALUES ('s1', 'p1', 'completed', 'claude', 'llm')"
        )
        conn.commit()
        conn.close()

        init_db(tmp_db_path)

        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT status, engine_type, agent_mode FROM simulations WHERE id = 's1'").fetchone()
            assert row["status"] == "completed"
            assert row["engine_type"] == "claude"
            assert row["agent_mode"] == "llm"


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
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
        )


class TestTimingAPI:
    @pytest.mark.anyio
    async def test_patch_sets_timing(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 48, "minutes_per_round": 30
        })
        assert resp.status_code == 200

        resp = await client.get(f"/api/simulations/{sim_id}")
        data = resp.json()["data"]
        assert data["total_hours"] == 48
        assert data["minutes_per_round"] == 30

    @pytest.mark.anyio
    async def test_fresh_simulation_has_null_timing(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]

        resp = await client.get(f"/api/simulations/{sim_id}")
        data = resp.json()["data"]
        assert data["total_hours"] is None
        assert data["minutes_per_round"] is None

    @pytest.mark.anyio
    async def test_patch_accepts_boundary_values(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 1, "minutes_per_round": 10
        })
        assert resp.status_code == 200

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 168, "minutes_per_round": 60
        })
        assert resp.status_code == 200

    @pytest.mark.anyio
    async def test_patch_rejects_out_of_range_hours(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 0
        })
        assert resp.status_code == 422

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 200
        })
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_patch_rejects_out_of_range_interval(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "minutes_per_round": 5
        })
        assert resp.status_code == 422

        resp = await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "minutes_per_round": 90
        })
        assert resp.status_code == 422

    @pytest.mark.anyio
    async def test_list_includes_timing(self, client, tmp_db_path):
        _create_project(tmp_db_path)
        resp = await client.post("/api/simulations", json={"project_id": "p1"})
        sim_id = resp.json()["data"]["id"]
        await client.patch(f"/api/simulations/{sim_id}/settings", json={
            "total_hours": 6, "minutes_per_round": 30
        })

        resp = await client.get("/api/simulations")
        sims = resp.json()["data"]
        sim = next(s for s in sims if s["id"] == sim_id)
        assert sim["total_hours"] == 6
        assert sim["minutes_per_round"] == 30


def _make_profiles(count=2):
    return [
        AgentProfile(
            agent_id=i, name=f"Agent {i}", username=f"agent{i}", bio=f"Bio {i}",
            persona=f"Persona {i}", age=30 + i, gender="nonbinary",
            profession="Analyst", interests=["data"],
            entity_type="Person", entity_source=f"Entity {i}",
        )
        for i in range(count)
    ]


def _mock_config_response():
    config_json = json.dumps({
        "total_hours": 48, "minutes_per_round": 30,
        "peak_hours": [9, 10, 17, 18], "off_peak_hours": [0, 1, 2, 3],
        "peak_multiplier": 1.5, "off_peak_multiplier": 0.3,
        "seed_posts": ["Breaking news"], "hot_topics": ["policy"],
        "narrative_direction": "escalating",
        "agent_configs": [{"agent_id": 0, "activity_level": 0.7}],
        "platform_config": {"feed_weights": {"recency": 0.4}},
    })
    return LLMResponse(text=config_json, input_tokens=800, output_tokens=600)


class TestConfigGeneratorTimingOverride:
    def test_user_timing_overrides_llm(self):
        client = MagicMock()
        client.smart_call.return_value = _mock_config_response()

        config, tokens = generate_config(
            client=client,
            profiles=_make_profiles(2),
            requirement="Predict impact",
            config_template="Entities: {{ entities_summary }}",
            user_total_hours=6.0,
            user_minutes_per_round=30,
        )

        assert config.total_hours == 6.0
        assert config.minutes_per_round == 30
        client.smart_call.assert_called_once()
        assert config.seed_posts == ["Breaking news"]
        assert config.hot_topics == ["policy"]

    def test_no_user_timing_uses_llm_values(self):
        client = MagicMock()
        client.smart_call.return_value = _mock_config_response()

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(2),
            requirement="Predict impact",
            config_template="Entities: {{ entities_summary }}",
        )

        assert config.total_hours == 48
        assert config.minutes_per_round == 30

    def test_partial_user_timing_uses_llm(self):
        """If only one timing value is provided, both come from LLM."""
        client = MagicMock()
        client.smart_call.return_value = _mock_config_response()

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(2),
            requirement="Predict impact",
            config_template="Entities: {{ entities_summary }}",
            user_total_hours=6.0,
            user_minutes_per_round=None,
        )

        assert config.total_hours == 48  # LLM value, not 6.0

    def test_user_timing_not_clamped_to_llm_ranges(self):
        """User values can go below the LLM clamp minimum (e.g., 1 hour)."""
        client = MagicMock()
        client.smart_call.return_value = _mock_config_response()

        config, _ = generate_config(
            client=client,
            profiles=_make_profiles(2),
            requirement="Predict impact",
            config_template="Entities: {{ entities_summary }}",
            user_total_hours=1.0,
            user_minutes_per_round=10,
        )

        assert config.total_hours == 1.0  # Below LLM clamp minimum of 12
        assert config.minutes_per_round == 10  # Below LLM clamp minimum of 15


class TestPreparePassesTiming:
    def test_prepare_reads_timing_from_db(self, tmp_db_path, tmp_data_dir, tmp_domains_dir):
        """When timing columns have values, they are passed to generate_config."""
        from unittest.mock import patch, MagicMock
        from forkcast.simulation.prepare import prepare_simulation
        from forkcast.llm.client import ClaudeClient

        # Set up DB with timing values
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
            )
            conn.execute(
                "INSERT INTO graphs (id, project_id, status, node_count, edge_count, file_path) "
                "VALUES ('g1', 'p1', 'complete', 2, 1, ?)",
                (str(tmp_data_dir / "p1" / "graph.json"),)
            )
            conn.execute(
                "INSERT INTO simulations (id, project_id, graph_id, status, total_hours, minutes_per_round) "
                "VALUES ('s1', 'p1', 'g1', 'created', 6.0, 30)"
            )

        # Create minimal graph file
        graph_dir = tmp_data_dir / "p1"
        graph_dir.mkdir(parents=True, exist_ok=True)
        graph_file = graph_dir / "graph.json"
        graph_file.write_text(json.dumps({
            "nodes": [{"id": "Alice", "type": "Person", "description": "researcher"}],
            "edges": [],
        }))

        client = MagicMock(spec=ClaudeClient)

        with patch("forkcast.simulation.prepare.generate_profiles_batched") as mock_gen_profiles, \
             patch("forkcast.simulation.prepare.generate_config") as mock_gen_config:

            mock_gen_profiles.return_value = (_make_profiles(1), [{"input": 0, "output": 0}])
            mock_gen_config.return_value = (MagicMock(to_dict=lambda: {}), {"input": 0, "output": 0})

            prepare_simulation(
                db_path=tmp_db_path,
                data_dir=tmp_data_dir,
                simulation_id="s1",
                client=client,
                domains_dir=tmp_domains_dir,
            )

            # Verify generate_config was called with user timing
            call_kwargs = mock_gen_config.call_args.kwargs
            assert call_kwargs.get("user_total_hours") == 6.0
            assert call_kwargs.get("user_minutes_per_round") == 30
