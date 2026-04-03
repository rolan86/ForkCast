"""Tests for V5→V6 DB schema migration (simulation_id column on token_usage)."""

import sqlite3
from pathlib import Path

import pytest

from forkcast.db.connection import get_db, init_db
from forkcast.db.schema import TABLES_V5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_names(conn: sqlite3.Connection, table: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return [row[1] for row in rows]


def _index_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return [row[0] for row in rows]


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return int(row[0])


def _build_v5_db(db_path: Path) -> None:
    """Create a V5 database (without the V6 migration) for upgrade tests."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(TABLES_V5)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', '5')"
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_fresh_db_has_simulation_id_column(tmp_path: Path) -> None:
    """Fresh DB should have simulation_id column in token_usage."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        columns = _column_names(conn, "token_usage")
    finally:
        conn.close()

    assert "simulation_id" in columns, (
        f"Expected 'simulation_id' column in token_usage. Got: {columns}"
    )


def test_fresh_db_version_is_6(tmp_path: Path) -> None:
    """Fresh DB should be at schema version 7 (latest)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        version = _schema_version(conn)
    finally:
        conn.close()

    assert version == 7, f"Expected schema version 7, got {version}"


def test_v5_to_v6_migration_adds_simulation_id(tmp_path: Path) -> None:
    """Existing V5 DB gains simulation_id column after migration, existing rows get NULL."""
    db_path = tmp_path / "test.db"

    # Build a V5 database and insert a row without simulation_id
    _build_v5_db(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "INSERT INTO token_usage (project_id, stage, input_tokens, output_tokens) "
            "VALUES (NULL, 'graph', 100, 200)"
        )
        conn.commit()
        pre_columns = _column_names(conn, "token_usage")
    finally:
        conn.close()

    assert "simulation_id" not in pre_columns, (
        "V5 DB should NOT have simulation_id before migration"
    )

    # Run migration via init_db
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        post_columns = _column_names(conn, "token_usage")
        row = conn.execute(
            "SELECT simulation_id FROM token_usage WHERE stage = 'graph'"
        ).fetchone()
        version = _schema_version(conn)
    finally:
        conn.close()

    assert "simulation_id" in post_columns, (
        f"After migration, token_usage should have simulation_id. Got: {post_columns}"
    )
    assert row is not None, "Pre-existing row should still be present after migration"
    assert row[0] is None, (
        f"Pre-existing row should have NULL simulation_id, got {row[0]!r}"
    )
    assert version == 7, f"Expected schema version 7 after migration, got {version}"


def test_v6_token_usage_index_exists(tmp_path: Path) -> None:
    """V6 DB should have index on token_usage(simulation_id)."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        indexes = _index_names(conn)
    finally:
        conn.close()

    assert "idx_token_usage_simulation_id" in indexes, (
        f"Expected index 'idx_token_usage_simulation_id'. Found: {indexes}"
    )
