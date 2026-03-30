"""Tests for schema v1→v2 migration."""

import sqlite3
from pathlib import Path

from forkcast.db.connection import get_db, init_db
from forkcast.db.schema import SCHEMA_VERSION


class TestSchemaVersion:
    def test_schema_version_is_6(self):
        assert SCHEMA_VERSION == 6

    def test_fresh_db_has_conversation_id(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(chat_history)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "conversation_id" in columns
            assert "report_id" not in columns

    def test_fresh_db_has_agent_action_index(self, tmp_db_path):
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_actions_agent'"
            ).fetchall()
            assert len(indexes) == 1

    def test_conversation_id_has_no_fk_constraint(self, tmp_db_path):
        """conversation_id should accept values not in the reports table."""
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO chat_history (conversation_id, role, message) "
                "VALUES (?, ?, ?)",
                ("agent_chat_sim1_0", "user", "Hello"),
            )
            row = conn.execute("SELECT * FROM chat_history WHERE conversation_id = ?", ("agent_chat_sim1_0",)).fetchone()
            assert row is not None


class TestV1ToV2Migration:
    def _create_v1_db(self, db_path: Path):
        """Create a v1 database with the old schema."""
        from forkcast.db.schema import TABLES_V1
        conn = sqlite3.connect(str(db_path))
        conn.executescript(TABLES_V1)
        conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '1')")
        conn.commit()
        conn.close()

    def test_migration_renames_column(self, tmp_db_path):
        self._create_v1_db(tmp_db_path)
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            cursor = conn.execute("PRAGMA table_info(chat_history)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "conversation_id" in columns
            assert "report_id" not in columns

    def test_migration_updates_version(self, tmp_db_path):
        self._create_v1_db(tmp_db_path)
        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            version = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            assert version[0] == "6"

    def test_migration_preserves_existing_data(self, tmp_db_path):
        self._create_v1_db(tmp_db_path)
        conn = sqlite3.connect(str(tmp_db_path))
        conn.execute("INSERT INTO projects (id, domain, name, status, requirement, created_at) VALUES ('p1','_default','T','ready','R',datetime('now'))")
        conn.execute("INSERT INTO simulations (id, project_id, status) VALUES ('s1','p1','completed')")
        conn.execute("INSERT INTO reports (id, simulation_id, status, created_at) VALUES ('r1','s1','completed',datetime('now'))")
        conn.execute("INSERT INTO chat_history (report_id, role, message) VALUES ('r1','user','Hello')")
        conn.commit()
        conn.close()

        init_db(tmp_db_path)
        with get_db(tmp_db_path) as conn:
            row = conn.execute("SELECT conversation_id FROM chat_history").fetchone()
            assert row["conversation_id"] == "r1"
