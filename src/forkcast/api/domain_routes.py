"""Domain management API routes."""

from pydantic import BaseModel

from fastapi import APIRouter

from forkcast.api.responses import error, success
from forkcast.config import get_settings
from forkcast.domains.loader import list_domains
from forkcast.domains.scaffold import DomainExistsError, scaffold_domain

router = APIRouter(prefix="/api/domains", tags=["domains"])


class CreateDomainRequest(BaseModel):
    name: str
    description: str
    language: str = "en"
    sim_engine: str = "claude"
    platforms: list[str] = ["twitter", "reddit"]


@router.get("")
async def get_domains():
    """List all available domain plugins."""
    settings = get_settings()
    domains = list_domains(settings.domains_dir)
    return success(
        [
            {
                "name": d.name,
                "version": d.version,
                "description": d.description,
                "language": d.language,
                "sim_engine": d.sim_engine,
                "platforms": d.platforms,
            }
            for d in domains
        ]
    )


@router.post("", status_code=201)
async def create_domain(req: CreateDomainRequest):
    """Scaffold a new domain plugin directory."""
    settings = get_settings()
    try:
        path = scaffold_domain(
            name=req.name,
            description=req.description,
            language=req.language,
            sim_engine=req.sim_engine,
            platforms=req.platforms,
            domains_dir=settings.domains_dir,
        )
    except DomainExistsError as e:
        return error(str(e), status_code=409)

    return success(
        {
            "name": req.name,
            "description": req.description,
            "language": req.language,
            "sim_engine": req.sim_engine,
            "platforms": req.platforms,
            "path": str(path),
        },
        status_code=201,
    )
