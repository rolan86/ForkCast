"""Tests for simulation timing controls — schema, API, and config generator."""

import sqlite3
from pathlib import Path

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.db.schema import SCHEMA_VERSION


class TestSchemaV5:
    def test_schema_version_is_5(self):
        assert SCHEMA_VERSION == 5

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
