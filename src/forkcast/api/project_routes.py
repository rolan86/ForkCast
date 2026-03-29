"""Project management API routes."""

import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.db.connection import get_db

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _generate_id() -> str:
    return f"proj_{secrets.token_hex(6)}"


@router.post("")
async def create_project(
    domain: Annotated[str, Form()],
    requirement: Annotated[str, Form()],
    files: list[UploadFile] = File(...),
    name: Annotated[str | None, Form()] = None,
):
    """Create a new project with uploaded files."""
    settings = get_settings()
    project_id = _generate_id()
    project_name = name or f"Project {project_id[-6:]}"
    now = datetime.now(timezone.utc).isoformat()

    # Create project directory
    project_dir = settings.data_dir / project_id
    uploads_dir = project_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Save files
    saved_files = []
    for f in files:
        content = await f.read()
        file_path = uploads_dir / f.filename
        file_path.write_bytes(content)
        saved_files.append(
            {
                "filename": f.filename,
                "path": str(file_path),
                "size": len(content),
            }
        )

    # Insert into database
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, domain, project_name, "created", requirement, now),
        )
        for sf in saved_files:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, sf["filename"], sf["path"], sf["size"], now),
            )

    return success(
        {
            "id": project_id,
            "name": project_name,
            "domain": domain,
            "status": "created",
            "requirement": requirement,
            "files": saved_files,
            "created_at": now,
        },
        status_code=201,
    )


class InlineDocument(BaseModel):
    filename: str
    content: str


class CreateProjectFromTextRequest(BaseModel):
    domain: str
    requirement: str
    name: str | None = None
    documents: list[InlineDocument] | None = None


@router.post("/from-text")
async def create_project_from_text(req: CreateProjectFromTextRequest):
    """Create a new project with inline document content (JSON body)."""
    settings = get_settings()

    # Validate domain exists
    domain_dir = settings.domains_dir / req.domain
    if not domain_dir.is_dir():
        return error(f"Domain not found: {req.domain}", status_code=400)

    # Validate documents
    if not req.documents:
        return error("At least one document is required", status_code=400)
    for doc in req.documents:
        if not doc.filename.strip():
            return error("Document filename must not be empty", status_code=400)
        if not doc.content.strip():
            return error("Document content must not be empty", status_code=400)

    project_id = _generate_id()
    project_name = req.name or f"Project {project_id[-6:]}"
    now = datetime.now(timezone.utc).isoformat()

    # Create project directory and write files
    project_dir = settings.data_dir / project_id
    uploads_dir = project_dir / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    saved_files = []
    for doc in req.documents:
        file_path = (uploads_dir / doc.filename).resolve()
        if not str(file_path).startswith(str(uploads_dir.resolve())):
            return error(f"Invalid filename: {doc.filename}", status_code=400)
        file_path.write_text(doc.content, encoding="utf-8")
        saved_files.append(
            {
                "filename": doc.filename,
                "path": str(file_path),
                "size": len(doc.content.encode("utf-8")),
            }
        )

    # Insert into database
    with get_db(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO projects (id, domain, name, status, requirement, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, req.domain, project_name, "created", req.requirement, now),
        )
        for sf in saved_files:
            conn.execute(
                "INSERT INTO project_files (project_id, filename, path, size, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (project_id, sf["filename"], sf["path"], sf["size"], now),
            )

    return success(
        {
            "id": project_id,
            "name": project_name,
            "domain": req.domain,
            "status": "created",
            "requirement": req.requirement,
            "files": saved_files,
            "created_at": now,
        },
        status_code=201,
    )


@router.get("")
async def list_projects():
    """List all projects."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        rows = conn.execute(
            "SELECT id, domain, name, status, requirement, created_at, updated_at "
            "FROM projects ORDER BY created_at DESC"
        ).fetchall()

    return success([dict(row) for row in rows])


@router.get("/{project_id}")
async def get_project(project_id: str):
    """Get project details by ID."""
    settings = get_settings()
    with get_db(settings.db_path) as conn:
        row = conn.execute(
            "SELECT id, domain, name, status, ontology_json, requirement, created_at, updated_at "
            "FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()

        if row is None:
            return error(f"Project not found: {project_id}", status_code=404)

        files = conn.execute(
            "SELECT filename, path, size FROM project_files WHERE project_id = ?",
            (project_id,),
        ).fetchall()

    project = dict(row)
    project["files"] = [dict(f) for f in files]
    return success(project)
