"""CLI commands for project management."""

import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

import typer

from forkcast.config import get_settings
from forkcast.db.connection import get_db

project_app = typer.Typer(help="Manage projects", no_args_is_help=True)


@project_app.command("create")
def project_create(
    files: Annotated[list[Path], typer.Argument(help="Files to upload (PDF, MD, TXT)")],
    domain: Annotated[str, typer.Option(help="Domain plugin name")] = "_default",
    prompt: Annotated[str, typer.Option(help="Prediction requirement / question")] = "",
    name: Annotated[str | None, typer.Option(help="Project name")] = None,
):
    """Create a new project from uploaded files."""
    if not prompt:
        typer.echo("Error: --prompt is required", err=True)
        raise typer.Exit(code=1)

    for f in files:
        if not f.exists():
            typer.echo(f"Error: File not found: {f}", err=True)
            raise typer.Exit(code=1)

    settings = get_settings()
    project_id = f"proj_{secrets.token_hex(6)}"
    project_name = name or f"Project {project_id[-6:]}"
    now = datetime.now(timezone.utc).isoformat()

    # Create project directory and copy files
    project_dir = settings.data_dir / project_id / "uploads"
    project_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for f in files:
        dest = project_dir / f.name
        shutil.copy2(f, dest)
        saved_files.append({"filename": f.name, "path": str(dest), "size": f.stat().st_size})

    # Insert into database
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, domain, project_name, "created", prompt, now),
        )
        for sf in saved_files:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, sf["filename"], sf["path"], sf["size"], now),
            )

    typer.echo(f"Project created: {project_id}")
    typer.echo(f"  Name:   {project_name}")
    typer.echo(f"  Domain: {domain}")
    typer.echo(f"  Files:  {len(saved_files)}")


@project_app.command("list")
def project_list():
    """List all projects."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, domain, name, status, requirement, created_at "
            "FROM projects ORDER BY created_at DESC"
        ).fetchall()

    if not rows:
        typer.echo("No projects found.")
        return

    typer.echo(f"{'ID':<20} {'Domain':<20} {'Status':<12} {'Name'}")
    typer.echo("-" * 80)
    for row in rows:
        typer.echo(f"{row['id']:<20} {row['domain']:<20} {row['status']:<12} {row['name']}")


@project_app.command("show")
def project_show(project_id: str):
    """Show project details."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if row is None:
            typer.echo(f"Project not found: {project_id}", err=True)
            raise typer.Exit(code=1)

        files = conn.execute(
            "SELECT filename, size FROM project_files WHERE project_id = ?",
            (project_id,),
        ).fetchall()

    typer.echo(f"ID:          {row['id']}")
    typer.echo(f"Name:        {row['name']}")
    typer.echo(f"Domain:      {row['domain']}")
    typer.echo(f"Status:      {row['status']}")
    typer.echo(f"Requirement: {row['requirement']}")
    typer.echo(f"Created:     {row['created_at']}")
    if files:
        typer.echo(f"\nFiles ({len(files)}):")
        for f in files:
            typer.echo(f"  - {f['filename']} ({f['size']} bytes)")
