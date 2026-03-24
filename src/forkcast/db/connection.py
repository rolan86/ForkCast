"""Database connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from forkcast.db.schema import MIGRATION_V1_TO_V2, MIGRATION_V2_TO_V3, MIGRATION_V3_TO_V4, MIGRATION_V4_TO_V5, SCHEMA_VERSION, TABLES_V1, TABLES_V5


def init_db(db_path: Path) -> None:
    """Initialize the database, creating tables or migrating if needed."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        existing_version = None
        try:
            row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
            if row:
                existing_version = int(row[0])
        except sqlite3.OperationalError:
            pass  # meta table doesn't exist — fresh DB

        if existing_version is None:
            conn.executescript(TABLES_V5)
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            conn.commit()
        elif existing_version < SCHEMA_VERSION:
            if existing_version == 1:
                conn.executescript(MIGRATION_V1_TO_V2)
                conn.commit()
                existing_version = 2
            if existing_version == 2:
                conn.executescript(MIGRATION_V2_TO_V3)
                conn.commit()
                existing_version = 3
            if existing_version == 3:
                conn.executescript(MIGRATION_V3_TO_V4)
                conn.commit()
                existing_version = 4
            if existing_version == 4:
                conn.executescript(MIGRATION_V4_TO_V5)
                conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Get a database connection as a context manager."""
    init_db(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
