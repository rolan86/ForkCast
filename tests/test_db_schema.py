import sqlite3
from pathlib import Path


class TestMigrationV3ToV4:
    """Tests for V3 → V4 migration adding agent_mode column."""

    def test_migration_adds_agent_mode_column(self, tmp_db_path):
        """Migrating a V3 DB should add agent_mode column and bump version to 4."""
        from forkcast.db.schema import TABLES_V3

        # Create a V3 database manually
        conn = sqlite3.connect(tmp_db_path)
        conn.executescript(TABLES_V3)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '3')"
        )
        conn.commit()
        conn.close()

        # Run init_db which should trigger V3→V4 migration
        from forkcast.db.connection import init_db

        init_db(tmp_db_path)

        conn = sqlite3.connect(tmp_db_path)
        # Check schema version is now 5 (migration chain runs to latest)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == "5"

        # Check agent_mode column exists with default 'llm'
        cols = [
            info[1]
            for info in conn.execute("PRAGMA table_info(simulations)").fetchall()
        ]
        assert "agent_mode" in cols

        # Verify default value
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES ('p1', '_default', 'Test', 'created', 'req', datetime('now'))"
        )
        conn.execute(
            "INSERT INTO simulations (id, project_id) VALUES ('s1', 'p1')"
        )
        row = conn.execute(
            "SELECT agent_mode FROM simulations WHERE id = 's1'"
        ).fetchone()
        conn.close()
        assert row[0] == "llm"

    def test_fresh_db_has_agent_mode_column(self, tmp_db_path):
        """A fresh database should include agent_mode column at version 5."""
        from forkcast.db.connection import init_db

        init_db(tmp_db_path)

        conn = sqlite3.connect(tmp_db_path)
        # Check version
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        assert row[0] == "5"

        # Check agent_mode column exists
        cols = [
            info[1]
            for info in conn.execute("PRAGMA table_info(simulations)").fetchall()
        ]
        assert "agent_mode" in cols
        conn.close()


def test_init_db_creates_tables(tmp_db_path):
    """init_db should create all required tables."""
    from forkcast.db.connection import init_db

    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    expected = {
        "meta",
        "projects",
        "project_files",
        "graphs",
        "simulations",
        "simulation_actions",
        "reports",
        "chat_history",
        "token_usage",
    }
    assert expected.issubset(tables), f"Missing tables: {expected - tables}"


def test_init_db_sets_schema_version(tmp_db_path):
    """init_db should set schema_version in meta table."""
    from forkcast.db.connection import init_db
    from forkcast.db.schema import SCHEMA_VERSION

    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    conn.close()

    assert row is not None
    assert int(row[0]) == SCHEMA_VERSION


def test_init_db_is_idempotent(tmp_db_path):
    """Calling init_db twice should not error or lose data."""
    from forkcast.db.connection import init_db

    init_db(tmp_db_path)
    init_db(tmp_db_path)

    conn = sqlite3.connect(tmp_db_path)
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "projects" in tables


def test_get_db_context_manager(tmp_db_path):
    """get_db should yield a working connection and auto-commit."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    with get_db(tmp_db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, datetime('now'))",
            ("proj_001", "_default", "Test", "created", "Test requirement"),
        )

    # Verify data persisted after context exit
    verify = sqlite3.connect(tmp_db_path)
    row = verify.execute("SELECT name FROM projects WHERE id = 'proj_001'").fetchone()
    verify.close()
    assert row[0] == "Test"


def test_get_db_rolls_back_on_error(tmp_db_path):
    """get_db should rollback on exception."""
    from forkcast.db.connection import get_db, init_db

    init_db(tmp_db_path)

    try:
        with get_db(tmp_db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
                "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                ("proj_002", "_default", "Fail", "created", "Test"),
            )
            raise ValueError("Simulated error")
    except ValueError:
        pass

    verify = sqlite3.connect(tmp_db_path)
    row = verify.execute("SELECT id FROM projects WHERE id = 'proj_002'").fetchone()
    verify.close()
    assert row is None
