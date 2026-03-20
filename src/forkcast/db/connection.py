"""SQLite connection management."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from forkcast.db.schema import SCHEMA_VERSION, TABLES_V1


def init_db(db_path: Path) -> None:
    """Initialize database with schema. Safe to call multiple times."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript(TABLES_V1)
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    conn.close()


@contextmanager
def get_db(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager that yields a connection, commits on success, rolls back on error."""
    conn = sqlite3.connect(db_path)
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
