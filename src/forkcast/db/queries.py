"""Shared database query helpers."""

from pathlib import Path

from forkcast.db.connection import get_db


def get_project_domain(db_path: Path, project_id: str) -> str:
    """Get the domain name for a project, defaulting to '_default'."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT domain FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    if row is None:
        return "_default"
    return row["domain"]


def get_domain_for_simulation(db_path: Path, simulation_id: str) -> str:
    """Get the domain name for a simulation via its project, defaulting to '_default'."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT p.domain FROM simulations s "
            "JOIN projects p ON s.project_id = p.id "
            "WHERE s.id = ?",
            (simulation_id,),
        ).fetchone()
    if row is None:
        return "_default"
    return row["domain"]
