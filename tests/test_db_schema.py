import sqlite3
from pathlib import Path


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
