"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from forkcast import __version__
from forkcast.api.responses import success
from forkcast.config import get_settings
from forkcast.db.connection import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    init_db(settings.db_path)
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="ForkCast",
        description="Collective intelligence simulation platform",
        version=__version__,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return success({"status": "ok", "service": "ForkCast", "version": __version__})

    # Routers will be included here as they're built in later tasks

    return app
