"""Capabilities endpoint — reports available engines and models."""
from fastapi import APIRouter
from forkcast.api.responses import success
from forkcast.config import AVAILABLE_MODELS

router = APIRouter(prefix="/api", tags=["capabilities"])


def _check_oasis() -> dict:
    try:
        import oasis  # noqa: F401
        return {"available": True}
    except ImportError:
        return {"available": False, "reason": "camel-oasis not installed"}


@router.get("/capabilities")
async def get_capabilities():
    return success({
        "engines": {
            "claude": {"available": True},
            "oasis": _check_oasis(),
        },
        "models": AVAILABLE_MODELS,
    })
