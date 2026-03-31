"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return success({"status": "ok", "service": "ForkCast", "version": __version__})

    from forkcast.api.domain_routes import router as domain_router
    app.include_router(domain_router)

    from forkcast.api.project_routes import router as project_router
    app.include_router(project_router)

    from forkcast.api.graph_routes import router as graph_router
    app.include_router(graph_router)

    from forkcast.api.simulation_routes import router as simulation_router
    app.include_router(simulation_router)

    from forkcast.api.report_routes import router as report_router
    app.include_router(report_router)

    from forkcast.api.capabilities_routes import router as capabilities_router
    app.include_router(capabilities_router)

    from forkcast.api.interact_routes import router as interact_router
    app.include_router(interact_router)

    return app
